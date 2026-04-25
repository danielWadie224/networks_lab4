import socket
import struct
import hashlib
import random

class RDTProtocol:
    def __init__(self, probability_loss=0.0, probability_corrupt=0.0):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sock.settimeout(2.0) 
        self.seq_num = 0 
        self.prob_loss = probability_loss
        self.prob_corrupt = probability_corrupt
        self.force_bad_checksum = False # For explicit simulation
        
    def compute_checksum(self, data_bytes):
        return hashlib.md5(data_bytes).digest()

    def make_pkt(self, seq_num, is_ack, is_syn, is_fin, is_last, data):
        # Header: seq, ack, syn, fin, last (5 ints = 20 bytes) + checksum (16 bytes) = 36 bytes
        temp_header = struct.pack('iiiii', seq_num, is_ack, is_syn, is_fin, is_last)
        packet_checksum = self.compute_checksum(temp_header + data)
        
        if self.force_bad_checksum:
            # Simulate false checksum as requested
            packet_checksum = bytes([(b + 1) % 256 for b in packet_checksum])
            self.force_bad_checksum = False # Reset after one use
            
        final_header = struct.pack('iiiii16s', seq_num, is_ack, is_syn, is_fin, is_last, packet_checksum)
        return final_header + data
    
    def parse_pkt(self, packet):
        if len(packet) < 36:
            return None
        header = packet[:36]
        data = packet[36:]
        seq_num, is_ack, is_syn, is_fin, is_last, packet_checksum = struct.unpack('iiiii16s', header)
        return seq_num, is_ack, is_syn, is_fin, is_last, packet_checksum, data

    def is_corrupt(self, packet):
        parsed = self.parse_pkt(packet)
        if parsed is None: return True
        seq_num, is_ack, is_syn, is_fin, is_last, received_checksum, data = parsed
        temp_header = struct.pack('iiiii', seq_num, is_ack, is_syn, is_fin, is_last)
        expected_checksum = self.compute_checksum(temp_header + data)
        return received_checksum != expected_checksum

    def unreliable_send(self, packet, dest_addr):
        if random.random() < self.prob_loss:
            print(f"--- Loss Simulation: Packet to {dest_addr} dropped ---")
            return
        if random.random() < self.prob_corrupt:
            print(f"--- Corruption Simulation: Packet to {dest_addr} corrupted ---")
            if len(packet) > 36:
                packet = packet[:36] + bytes([packet[36] ^ 0xFF]) + packet[37:]
            else:
                packet = bytes([packet[0] ^ 0xFF]) + packet[1:]
        self.sock.sendto(packet, dest_addr)
    
    def rdt_send(self, data, dest_addr):
        """Sends potentially large data by fragmenting it."""
        chunk_size = 1024
        chunks = [data[i:i+chunk_size] for i in range(0, len(data), chunk_size)]
        
        for i, chunk in enumerate(chunks):
            is_last = 1 if i == len(chunks) - 1 else 0
            packet = self.make_pkt(self.seq_num, 0, 0, 0, is_last, chunk)
            
            while True:
                self.unreliable_send(packet, dest_addr)
                try:
                    ack_packet, addr = self.sock.recvfrom(2048)
                    if not self.is_corrupt(ack_packet):
                        parsed = self.parse_pkt(ack_packet)
                        if parsed and parsed[1] == 1 and parsed[0] == self.seq_num:
                            self.seq_num = 1 - self.seq_num
                            break 
                except socket.timeout:
                    print(f"Timeout waiting for ACK {self.seq_num}. Retransmitting...")

    def rdt_rcv(self):
        """Receives and reassembles fragmented packets."""
        full_data = b""
        while True:
            try:
                packet, addr = self.sock.recvfrom(4096)
                if self.is_corrupt(packet):
                    print("Received corrupted packet, dropping.")
                    continue
                
                parsed = self.parse_pkt(packet)
                if not parsed: continue
                rcv_seq, is_ack, is_syn, is_fin, is_last, _, data = parsed
                
                if is_fin:
                    ack_pkt = self.make_pkt(rcv_seq, 1, 0, 1, 1, b'')
                    self.unreliable_send(ack_pkt, addr)
                    return None, addr

                if rcv_seq == self.seq_num:
                    ack_pkt = self.make_pkt(self.seq_num, 1, 0, 0, 1, b'')
                    self.unreliable_send(ack_pkt, addr)
                    self.seq_num = 1 - self.seq_num
                    full_data += data
                    if is_last:
                        return full_data, addr
                else:
                    # Duplicate packet, resend ACK
                    ack_pkt = self.make_pkt(rcv_seq, 1, 0, 0, 1, b'')
                    self.unreliable_send(ack_pkt, addr)
            except socket.timeout:
                continue
        
    def connect(self, server_addr):
        self.seq_num = 0
        syn_pkt = self.make_pkt(0, 0, 1, 0, 1, b'')
        while True:
            print(f"Connecting to {server_addr}...")
            self.unreliable_send(syn_pkt, server_addr)
            try:
                resp_pkt, addr = self.sock.recvfrom(2048)
                if not self.is_corrupt(resp_pkt):
                    parsed = self.parse_pkt(resp_pkt)
                    if parsed and parsed[1] == 1 and parsed[2] == 1:
                        self.seq_num = 1
                        ack_pkt = self.make_pkt(1, 1, 0, 0, 1, b'')
                        self.unreliable_send(ack_pkt, addr)
                        print("Handshake complete (Client side).")
                        return True
            except socket.timeout:
                print("Handshake timeout, retrying SYN...")
        
    def accept(self):
        self.sock.settimeout(None)
        while True:
            packet, addr = self.sock.recvfrom(2048)
            if not self.is_corrupt(packet):
                parsed = self.parse_pkt(packet)
                if parsed and parsed[2] == 1:
                    print(f"SYN received from {addr}")
                    self.seq_num = 0
                    syn_ack = self.make_pkt(0, 1, 1, 0, 1, b'')
                    self.sock.settimeout(2.0)
                    while True:
                        self.unreliable_send(syn_ack, addr)
                        try:
                            ack_pkt, _ = self.sock.recvfrom(2048)
                            if not self.is_corrupt(ack_pkt) and self.parse_pkt(ack_pkt)[1] == 1:
                                self.seq_num = 1
                                print("Handshake complete (Server side).")
                                return addr
                        except socket.timeout:
                            break
                    self.sock.settimeout(None)

    def close(self, dest_addr):
        print(f"Closing connection to {dest_addr}...")
        fin_pkt = self.make_pkt(self.seq_num, 0, 0, 1, 1, b'')
        for _ in range(5):
            self.unreliable_send(fin_pkt, dest_addr)
            try:
                ack_packet, _ = self.sock.recvfrom(2048)
                if not self.is_corrupt(ack_packet):
                    parsed = self.parse_pkt(ack_packet)
                    if parsed and parsed[1] == 1 and parsed[3] == 1:
                        print("FIN ACK received.")
                        break
            except socket.timeout:
                pass
        self.sock.close()

    def bind(self, port):
        self.sock.bind(('', port))

    def simulate_false_checksum(self):
        """Method specially created to simulate a false checksum as per PDF requirement."""
        self.force_bad_checksum = True
