from rdt_protocol import RDTProtocol
import os
from datetime import datetime

def start_server():
    # Simulate 5% loss and 5% corruption
    rdt = RDTProtocol(probability_loss=0.05, probability_corrupt=0.05)
    rdt.bind(12345)
    
    print("Server is listening on port 12345...")
    
    while True:
        try:
            client_addr = rdt.accept()
            if not client_addr: continue
            print(f"\n--- New Connection from {client_addr} ---")
            
            request_data, _ = rdt.rdt_rcv()
            if request_data:
                request_str = request_data.decode()
                print(f"Received Request:\n{request_str}")
                
                lines = request_str.splitlines()
                if not lines: continue
                
                header_line = lines[0].split()
                if len(header_line) < 3: continue
                
                method = header_line[0]
                path = header_line[1].strip("/")
                if path == "": path = "index.html"

                response_body = b""
                status_code = "200 OK"

                if method == "GET":
                    if os.path.exists(path):
                        with open(path, "rb") as f:
                            response_body = f.read()
                    else:
                        status_code = "404 NOT FOUND"
                        response_body = b"File Not Found"
                
                elif method == "POST":
                    # For POST, we'll just acknowledge receiving the data and save it
                    content_length = 0
                    for line in lines:
                        if line.lower().startswith("content-length:"):
                            content_length = int(line.split(":")[1].strip())
                    
                    # In a real server, we'd read exactly content_length bytes from the body
                    # Here we assume the body is part of the received request_data
                    body_start = request_str.find("\r\n\r\n") + 4
                    body = request_data[body_start:]
                    
                    print(f"POST received for {path}. Body length: {len(body)}")
                    with open("posted_" + path, "wb") as f:
                        f.write(body)
                    
                    status_code = "200 OK"
                    response_body = f"Successfully received POST data for {path}".encode()

                # Build HTTP Response with Headers
                response_headers = [
                    f"HTTP/1.0 {status_code}",
                    f"Date: {datetime.now().strftime('%a, %d %b %Y %H:%M:%S GMT')}",
                    "Server: CustomRDTServer/1.0",
                    f"Content-Length: {len(response_body)}",
                    "Content-Type: text/html",
                    "Connection: close",
                    "\r\n"
                ]
                
                full_response = "\r\n".join(response_headers).encode() + response_body
                print(f"Sending {status_code} response...")
                rdt.rdt_send(full_response, client_addr)
            
            print("Closing connection...")
            rdt.close(client_addr)
            # Reset for next connection
            rdt = RDTProtocol(probability_loss=0.05, probability_corrupt=0.05)
            rdt.bind(12345)

        except Exception as e:
            print(f"Server error: {e}")
            rdt = RDTProtocol(probability_loss=0.05, probability_corrupt=0.05)
            rdt.bind(12345)

if __name__ == "__main__":
    start_server()
