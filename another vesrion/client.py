from rdt_protocol import RDTProtocol

def run_client():
    rdt = RDTProtocol()
    server_addr = ('127.0.0.1', 8080)
    
    # 1. Start Handshake 
    if rdt.connect(server_addr):
        # 2. Build HTTP GET Request [cite: 13, 27]
        # Make sure you have a file named 'test.txt' in the server directory
        http_get = "GET /test.txt HTTP/1.0\r\nHost: localhost\r\n\r\n"
        print(f"Sending Reliable GET:\n{http_get}")
        rdt.rdt_send(http_get.encode(), server_addr)
        
        # 3. Receive Reliable Response
        response, _, _ = rdt.rdt_rcv()
        print(f"--- Server Response ---\n{response.decode()}")
        
        # 4. Teardown
        rdt.close(server_addr)

if __name__ == "__main__":
    run_client()