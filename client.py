from rdt_protocol import RDTProtocol
import sys

def start_client(filename):
    # Simulate 10% loss and 10% corruption
    rdt = RDTProtocol(probability_loss=0.1, probability_corrupt=0.1)
    server_addr = ('127.0.0.1', 12345)
    
    print(f"Connecting to {server_addr}...")
    if rdt.connect(server_addr):
        print("Connected!")
        
        request = f"GET /{filename} HTTP/1.0\r\n\r\n"
        print(f"Sending request for {filename}...")
        rdt.rdt_send(request.encode(), server_addr)
        
        print("Waiting for response...")
        response_data, _ = rdt.rdt_rcv()
        if response_data:
            print("Response received:")
            print(response_data.decode())
        
        rdt.close(server_addr)
        print("Connection closed.")

if __name__ == "__main__":
    fname = sys.argv[1] if len(sys.argv) > 1 else "index.html"
    start_client(fname)
