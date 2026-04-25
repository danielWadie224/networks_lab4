import socket
import struct
import hashlib

class RDTProtocol:
    def __init__(self):
        # We use a standard UDP socket
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        # Timeout for our stop-and-wait protocol
        self.sock.settimeout(2.0) 
        # The sequence number for the next packet to send (0 or 1)
        self.seq_num = 0 
        
    def compute_checksum(self, data_bytes):
        """Creates a 16-byte MD5 checksum of the given bytes."""
        return hashlib.md5(data_bytes).digest()

    def make_pkt(self, seq_num, is_ack, is_syn, is_fin, data):
        """
        Packs the sequence number, control flags, checksum, and data.
        """
        # Step 1: Pack the header values (excluding the checksum itself)
        # We now have 4 integers (16 bytes total)
        temp_header = struct.pack('iiii', seq_num, is_ack, is_syn, is_fin)
        
        # Step 2: Calculate checksum over header + data [cite: 37, 41]
        packet_checksum = self.compute_checksum(temp_header + data)
        
        # Step 3: Pack the final header with the 16-byte MD5 hash
        # Format 'iiii16s' results in a 32-byte header
        final_header = struct.pack('iiii16s', seq_num, is_ack, is_syn, is_fin, packet_checksum)
        
        return final_header + data
    
    def parse_pkt(self, packet):
        header = packet[:32]
        data = packet[32:]
        
        # Unpacking the 4 flags and the checksum
        seq_num, is_ack, is_syn, is_fin, packet_checksum = struct.unpack('iiii16s', header)
        
        return seq_num, is_ack, is_syn, is_fin, packet_checksum, data

    def is_corrupt(self, packet):
        """
        Verifies if the packet was corrupted in transit.
        """
        seq_num, is_ack, received_checksum, data = self.parse_pkt(packet)
        
        # Rebuild the temporary header to calculate what the checksum SHOULD be
        temp_header = struct.pack('ii', seq_num, is_ack)
        expected_checksum = self.compute_checksum(temp_header + data)
        
        # If they don't match, the packet is corrupted
        return received_checksum != expected_checksum
    
    def rdt_send(self, data, dest_addr):
        # 1. Create the data packet with the current sequence number
        packet = self.make_pkt(self.seq_num, is_ack=0, data=data)

        # 2. The While Loop you suggested
        while True:
            # Send the packet
            self.sock.sendto(packet, dest_addr)

            try:
                # Wait for an ACK. If 2 seconds pass, this raises socket.timeout
                ack_packet, addr = self.sock.recvfrom(1024)

                # Parse the incoming packet
                rcv_seq, is_ack, _, _ = self.parse_pkt(ack_packet)

                # Verify it's a valid ACK for the packet we just sent
                if not self.is_corrupt(ack_packet) and is_ack == 1 and rcv_seq == self.seq_num:
                    # Success! Toggle seq_num (0 becomes 1, 1 becomes 0) 
                    self.seq_num = 1 - self.seq_num
                    break  # Exit the while loop, we are done sending this data
                else:
                    # Received a corrupted ACK or an ACK for the wrong sequence number.
                    # We do nothing and let the loop continue to wait for a timeout.
                    pass 

            except socket.timeout:
                # The timer "interrupt" fired! The loop will repeat and retransmit.
                print(f"Timeout waiting for ACK {self.seq_num}. Retransmitting...")
    
    def rdt_rcv(self):
        """Listens for an incoming reliable packet and returns the data."""
        while True:
            # 1. Wait for raw bytes from the network
            packet, addr = self.sock.recvfrom(2048)

            # 2. If it's corrupted, we just drop it (do nothing and wait for the next)
            if self.is_corrupt(packet):
                continue
            
            # 3. Parse the good packet
            rcv_seq, is_ack, _, data = self.parse_pkt(packet)
            
            if rcv_seq == self.seq_num:
                # SUCCESS! It's the exact sequence number we were waiting for.
                # Send the ACK for this sequence number
                ack_pkt = self.make_pkt(self.seq_num, is_ack=1, data=b'')
                self.sock.sendto(ack_pkt, addr)
                
                # Toggle our expected sequence number for the next time
                self.seq_num = 1 - self.seq_num
                
                # Return the data up to the Application Layer (the HTTP server)
                return data, addr
            else:
                # DUPLICATE! It's the wrong sequence number.
                # Re-send the ACK for the sequence number we just received.
                ack_pkt = self.make_pkt(rcv_seq, is_ack=1, data=b'')
                self.sock.sendto(ack_pkt, addr)
        
    def connect(self, server_addr):
        # 1. Start the 3-way handshake: Send SYN
        # We use seq_num=0 for the start (isn = 0)
        syn_pkt = self.make_pkt(seq_num=0, is_ack=0, is_syn=1, is_fin=0, data=b'')
        
        while True:
            print("Client: Sending SYN...")
            self.sock.sendto(syn_pkt, server_addr)
            
            try:
                # 2. Wait for SYN-ACK from server
                resp_pkt, addr = self.sock.recvfrom(2048)
                
                # Check for corruption and proper flags (ACK=1, SYN=1)
                if not self.is_corrupt(resp_pkt):
                    rcv_seq, is_ack, is_syn, is_fin, _, _ = self.parse_pkt(resp_pkt)
                    
                    if is_ack == 1 and is_syn == 1:
                        print("Client: Received SYN-ACK!")
                        # 3. Final Step: Send ACK back to server
                        # In simple RDT, we ACK the sequence we just got
                        final_ack = self.make_pkt(seq_num=rcv_seq, is_ack=1, is_syn=0, is_fin=0, data=b'')
                        self.sock.sendto(final_ack, addr)
                        
                        # Sync our internal sequence number to start data transfer
                        self.seq_num = (rcv_seq + 1) % 2
                        return True # Connection established!
            
            except socket.timeout:
                print("Client: Handshake timeout, retrying...")
        
    def accept(self):
        """Passive wait for a connection (Server side)."""
        print("Server: Waiting for SYN...")
        while True:
            # Step 1: Wait for SYN (no timeout here yet, just listening)
            self.sock.settimeout(None) 
            packet, addr = self.sock.recvfrom(2048)
            
            if not self.is_corrupt(packet):
                rcv_seq, is_ack, is_syn, is_fin, _, _ = self.parse_pkt(packet)
                
                if is_syn == 1:
                    print(f"Server: Received SYN from {addr}")
                    # Step 2: Prepare SYN-ACK
                    # We'll use the toggle logic: (rcv_seq + 1) % 2
                    server_seq = (rcv_seq + 1) % 2
                    syn_ack = self.make_pkt(seq_num=server_seq, is_ack=1, is_syn=1, is_fin=0, data=b'')
                    
                    # Step 3: Enter a loop with a timeout to wait for the final ACK
                    self.sock.settimeout(2.0)
                    while True:
                        self.sock.sendto(syn_ack, addr)
                        try:
                            ack_pkt, _ = self.sock.recvfrom(2048)
                            if not self.is_corrupt(ack_pkt):
                                a_seq, a_ack, a_syn, a_fin, _, _ = self.parse_pkt(ack_pkt)
                                # Final check: Is it an ACK for our SYN-ACK?
                                if a_ack == 1 and a_seq == server_seq:
                                    print("Server: Connection ESTABLISHED")
                                    return addr # Handshake complete!
                        except socket.timeout:
                            print("Server: Final ACK timeout, resending SYN-ACK...")