from rdt_protocol import RDTProtocol

def start_server():
    # Initialize RDT Server on port 8080
    rdt = RDTProtocol(is_server=True, port=8080)
    print("HTTP Server (over UDP) running on port 8080...")
    
    # Wait for the handshake 
    client_addr = rdt.accept()
    
    while True:
        # Receive the reliable data
        data, addr, is_fin = rdt.rdt_rcv()
        if is_fin: 
            print("Client requested teardown.")
            break
        
        request = data.decode()
        print(f"--- HTTP Request ---\n{request}")
        
        try:
            lines = request.split("\r\n")
            if not lines: continue
            method, path, _ = lines[0].split() 
            filename = path.strip("/")

            if method == "GET": 
                try:
                    with open(filename, "rb") as f:
                        body = f.read()
                    response = b"HTTP/1.0 200 OK\r\n\r\n" + body
                except FileNotFoundError:
                    response = b"HTTP/1.0 404 NOT FOUND\r\n\r\nFile Not Found" 
            
            elif method == "POST": 
                # Extracting body (everything after the double newline)
                body_content = request.split("\r\n\r\n")[1]
                with open(f"received_{filename}", "w") as f:
                    f.write(body_content)
                response = b"HTTP/1.0 200 OK\r\n\r\nFile Saved Successfully" 
            else:
                response = b"HTTP/1.0 400 BAD REQUEST\r\n\r\n"
        except Exception as e:
            response = b"HTTP/1.0 500 INTERNAL SERVER ERROR\r\n\r\n"
            print(f"Error parsing request: {e}")

        # Send the HTTP response back reliably
        rdt.rdt_send(response, addr)

if __name__ == "__main__":
    start_server()