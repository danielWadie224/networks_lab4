import socket
from rdt_protocol import RDTProtocol

def start_bridge():
    # 1. Listen for TCP from the Browser
    tcp_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    tcp_sock.bind(('127.0.0.1', 8888)) # Browser will connect here
    tcp_sock.listen(1)
    print("Bridge is active. Point your browser to http://127.0.0.1:8888/test.txt")

    # 2. Setup RDT to talk to your Server
    rdt = RDTProtocol()
    server_addr = ('127.0.0.1', 8080)

    while True:
        browser_conn, addr = tcp_sock.accept()
        request = browser_conn.recv(4096)
        
        if request:
            print("Bridge: Received TCP from Browser. Converting to RDT...")
            # Perform RDT Handshake and Send
            if rdt.connect(server_addr):
                rdt.rdt_send(request, server_addr)
                
                # Receive RDT response from Server
                rdt_response, _, _ = rdt.rdt_rcv()
                
                # Send back to Browser via TCP
                browser_conn.sendall(rdt_response)
                rdt.close(server_addr)
        
        browser_conn.close()

if __name__ == "__main__":
    start_bridge()