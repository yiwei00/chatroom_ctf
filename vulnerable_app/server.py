import socket
import threading
import time
from datetime import datetime
from collections import deque

TIMEOUT_SEC = 300
TICKS_PER_SEC = 30

HELP_MSG = b'''Commands:
    /help - show this message
    /quit - quit the chatroom
    /logs - show the log history for the current server'''

class _ChatClient:
    def __init__(self, sock=None, addr=None, **kwargs) -> None:
        default_kwargs = {
            'sock': sock,
            'addr': addr,
            'username': None,
            'thread': None
        }
        kwargs = {**default_kwargs, **kwargs}
        self.sock = kwargs['sock']
        self.addr = kwargs['addr']
        self.username = kwargs['username']
        self.thread = kwargs['thread']
        self.last_active = datetime.now()
    def activate(self) -> None:
        self.last_active = datetime.now()
    def __eq__(self, other: object) -> bool:
        if isinstance(other, _ChatClient):
            return self.addr == other.addr
        return False
    def __hash__(self) -> int:
        return hash(self.addr)



class ChatServer:
    def __init__(self, **kwargs) -> None:
        default_kwargs = {
            'max_clients': 5,
        }
        kwargs = {**default_kwargs, **kwargs}
        # args
        self.host = kwargs['host']
        self.port = kwargs['port']
        self.logger = kwargs['logger']
        self.max_clients = kwargs['max_clients']
        # other attributes
        self.running = False
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # keeping track of threads:
        self.accept_thread = None
        # _clients maps tcp socket to username
        self._clients = set()
        # _broadcast_queue is a queue of messages to be broadcasted
        self._broadcast_queue = deque()
        # Locks: r for running, bq for broadcast queue, cl for clients
        self._r_lock = threading.Lock()
        self._bq_lock = threading.Lock()
        self._cl_lock = threading.Lock()
        # track if at least one client has connected
        self._has_clients = False

        self.logger.log("Chatserver initialized with host={}, port={}, max_clients={}", self.host, self.port, self.max_clients)
        pass
    def run(self):
        # starting a socket server
        self.sock.settimeout(2)
        self.sock.bind((self.host, self.port))
        self.sock.listen(5)
        self.running = True
        # spawn a thread to accept clients
        self.accept_thread = threading.Thread(target=self.accept_client)
        self.accept_thread.start()
        # start server loop
        while True:
            with self._r_lock:
                if not self.running:
                    break
            #region kick inactive clients
            with self._cl_lock:
                for client in self._clients:
                    if (datetime.now() - client.last_active).seconds > TIMEOUT_SEC:
                        self.logger.log("Kicking {} due to inactivity.", client.addr)
                        client.sock.shutdown(socket.SHUT_RDWR)
                        client.thread.join()
            #endregion
            #region broadcast messages
            broadcast_queue = deque()
            with self._bq_lock:
                while self._broadcast_queue: #empty out the queue
                    broadcast_queue.append(self._broadcast_queue.popleft())
            while broadcast_queue:
                msg, origin = broadcast_queue.popleft()
                self.logger.log("Chatroom: {}", msg)
                with self._cl_lock:
                    for client in self._clients: # broadcast to all clients except origin
                        if client == origin:
                            continue
                        if not self.cl_sendall(client, msg.encode('utf-8')):
                            client.sock.shutdown(socket.SHUT_RDWR)
                            break
            #endregion
            #region remove disconnected clients
            client_list = None
            # save snapshot of _clients
            with self._cl_lock:
                client_list = list(self._clients)
            for client in client_list:
                if not client.thread.is_alive():
                    # remove from set
                    with self._cl_lock:
                        self._clients.remove(client)
                    # close socket
                    client.sock.close()
                    self.logger.log("Client {} disconnected.", client.addr)
                    if client.username:
                        self.broadcast(f"{client.username} has left the chat.")
            #endregion
            time.sleep(1/TICKS_PER_SEC)
        # just in case, lets join all client threads
        with self._cl_lock:
            for client in self._clients:
                client.sock.shutdown(socket.SHUT_RDWR)
                client.sock.close()
                client.thread.join()
        # join accept thread
        self.accept_thread.join()

    def stop(self):
        if not self.running:
            return
        self.logger.log("Stopping server.")
        with self._r_lock:
            self.running = False

    def accept_client(self):
        while True:
            with self._r_lock: # break if server is stopped
                if not self.running:
                    break
            try:
                client_sock, client_addr = self.sock.accept()
            except socket.timeout:
                continue
            if not client_sock:
                continue
            self.logger.log("Accepted connection from {}", client_addr)
            with self._cl_lock:
                if len(self._clients) >= self.max_clients:
                    try:
                        client_sock.sendall(b"Server full. Try again later.")
                    except socket.error:
                        self.logger.log("Unable to notify {} that server is full.", client_addr)
                    finally:
                        self.logger.log("Rejecting client {} (server full).", client_addr)
                        client_sock.close()
                else:
                    client = _ChatClient(client_sock, client_addr)
                    client.thread = threading.Thread(target=self.handle_client, args=(client,))
                    self._clients.add(client)
                    self._has_clients = True
                    client.thread.start()

    def broadcast(self, msg: str, origin: _ChatClient = None):
        with self._bq_lock:
            self._broadcast_queue.append((msg, origin))

    def cl_sendall(self, client: _ChatClient, msg: str):
        if type(msg) is str:
            msg = msg.encode('utf-8')
        try:
            client.sock.sendall(msg + b'\n')
        except socket.error:
            self.logger.log("Unable to send message to {}.", client.addr)
            return False
        else:
            client.activate()
            return True

    def cl_recv(self, client: _ChatClient):
        try:
            data = client.sock.recv(1024)
        except ConnectionAbortedError:
            return None
        except ConnectionResetError:
            return None
        if not data:
            return None
        client.activate()
        return data.decode('utf-8').strip()

    def handle_client(self, client: _ChatClient):
        #region ask for username
        if(
            not self.cl_sendall(client, b"Welcome to the chatroom!") or
            not self.cl_sendall(client, b"Please send your username consisting of 3-16 alphanumeric characters:")
        ):
            return
        while True: # loop until valid username is received
            data = self.cl_recv(client)
            if not data:
                return
            username = data
            if not username.isalnum() or len(username) < 3 or len(username) > 16:
                if not self.cl_sendall(client, b"Invalid username. Please try again: "):
                    return
                continue
            else:
                client.username = username
                break
        if (
            not self.cl_sendall(client, b"Welcome, " + username.encode('utf-8') + b"!") or
            not self.cl_sendall(client, b"Type /help for a list of commands.")
        ):
            return
        self.logger.log("Client {} logged in as {}.", client.addr, username)
        self.broadcast(f"{username} has joined the chatroom.", client)
        #endregion
        #region main loop
        while True:
            with self._r_lock:
                if not self.running:
                    break
            data = self.cl_recv(client)
            if not data:
                return
            if data[0] == '/':
                tokens = data.split()
                cmd = tokens[0]
                if cmd == '/quit':
                    return
                elif cmd == '/help':
                    self.cl_sendall(client, HELP_MSG)
                elif cmd == '/logs':
                    self.cl_sendall(client, b"Sending logs...")
                    log_str = self.logger.log_dump()
                    if log_str[-1] == '\n':
                        log_str = log_str[:-1]
                    self.cl_sendall(client, log_str.encode('utf-8'))
                    self.cl_sendall(client, b"End of logs. (Logged by Log4py)")
                else:
                    self.cl_sendall(client, b"Unknown command. Use /help for a list of commands.")
            else:
                self.broadcast(f"{username}: {data}", client)
        #endregion
