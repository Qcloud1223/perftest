import sys
import re
import os

# Constants
TSC_FREQUENCY = 2.1 * 10**9  # 2.1 GHz

def get_message_size_from_filename(filepath):
    filename = os.path.basename(filepath)
    match = re.search(r's(\d+)', filename)
    if match:
        return int(match.group(1))
    else:
        print(f"Error: Could not find size pattern 's[0-9]+' in filename '{filename}'.")
        sys.exit(1)

def process_bursts(input_path):
    base, ext = os.path.splitext(input_path)
    output_path = f"{base}_parsed{ext}"
    
    msg_size_bytes = get_message_size_from_filename(input_path)
    
    print(f"Reading from: {input_path}")
    print(f"Writing to:   {output_path}")
    
    # State Variables
    prev_ts = None
    
    # Global Accumulators (for overall average)
    first_ts = None
    last_ts = None
    total_msg_count = 0
    
    # Burst Accumulators
    burst_start_ts_ref = None 
    burst_end_ts = None       
    burst_msg_count = 0
    burst_line_count = 0
    burst_id = 1

    try:
        with open(input_path, 'r') as f_in, open(output_path, 'w') as f_out:
            # Header
            f_out.write(f"Source File: {input_path}\n")
            f_out.write(f"Message Size: {msg_size_bytes} bytes\n")
            f_out.write("-" * 90 + "\n")
            header = (f"{'Burst ID':<10} | {'Lines':<8} | {'Duration (us)':<15} | "
                      f"{'Total Msgs':<12} | {'Throughput (Gbps)':<18}\n")
            f_out.write(header)
            f_out.write("-" * 90 + "\n")

            for line_num, line in enumerate(f_in):
                line = line.strip()
                if not line: continue

                try:
                    parts = line.split(',')
                    curr_ts = int(parts[0])
                    curr_msgs = int(parts[1])
                    curr_polls = int(parts[2])
                except (ValueError, IndexError):
                    print(f"Skipping malformed line {line_num+1}")
                    continue

                # 1. Update Global Stats
                if first_ts is None:
                    first_ts = curr_ts
                last_ts = curr_ts
                total_msg_count += curr_msgs

                # 2. Initialize Logic (Handle first line)
                if prev_ts is None:
                    prev_ts = curr_ts
                    continue

                # 3. Burst Detection Logic
                # If polls > 0, the previous burst has ended; new one begins.
                if curr_polls > 0:
                    # Finalize previous burst
                    if burst_line_count > 0:
                        write_burst_stats(f_out, burst_id, burst_start_ts_ref, burst_end_ts, 
                                          burst_msg_count, burst_line_count, msg_size_bytes)
                        burst_id += 1

                    # Start new burst
                    burst_start_ts_ref = prev_ts
                    burst_msg_count = curr_msgs
                    burst_line_count = 1
                    burst_end_ts = curr_ts
                
                else:
                    # Continue current burst
                    if burst_line_count == 0:
                        burst_start_ts_ref = prev_ts # Edge case for file start
                        
                    burst_msg_count += curr_msgs
                    burst_line_count += 1
                    burst_end_ts = curr_ts

                prev_ts = curr_ts

            # End of file: Write the final pending burst
            if burst_line_count > 0:
                write_burst_stats(f_out, burst_id, burst_start_ts_ref, burst_end_ts, 
                                  burst_msg_count, burst_line_count, msg_size_bytes)

            # ---------------------------------------------------------
            # Calculate and Write Global Average
            # ---------------------------------------------------------
            f_out.write("-" * 90 + "\n")
            
            if first_ts is not None and last_ts is not None and last_ts > first_ts:
                global_duration_sec = (last_ts - first_ts) / TSC_FREQUENCY
                global_bits = total_msg_count * msg_size_bytes * 8
                global_gbps = (global_bits / global_duration_sec) / 1e9
                
                summary = (f"GLOBAL SUMMARY:\n"
                           f"  Total Duration: {global_duration_sec:.6f} sec\n"
                           f"  Total Messages: {total_msg_count}\n"
                           f"  Average Throughput: {global_gbps:.4f} Gbps\n")
                
                f_out.write(summary)
                print(summary) # Also print to console
            else:
                f_out.write("Global Summary: Insufficient data or duration is zero.\n")

        print("Done.")

    except FileNotFoundError:
        print(f"Error: File '{input_path}' not found.")
    except PermissionError:
        print(f"Error: Permission denied writing to '{output_path}'.")

def write_burst_stats(f_out, b_id, start_ts, end_ts, msg_count, line_count, size_bytes):
    """Calculates metrics and writes a row to the file."""
    if start_ts is None or end_ts is None:
        return

    delta_ts = end_ts - start_ts

    if delta_ts > 0:
        duration_seconds = delta_ts / TSC_FREQUENCY
        total_bits = msg_count * size_bytes * 8
        gbps = (total_bits / duration_seconds) / 1e9
        duration_us = duration_seconds * 1e6

        f_out.write(f"{b_id:<10} | {line_count:<8} | {duration_us:<15.3f} | "
                    f"{msg_count:<12} | {gbps:<18.4f}\n")
    else:
        f_out.write(f"{b_id:<10} | {line_count:<8} | {'0.000':<15} | "
                    f"{msg_count:<12} | {'N/A':<18}\n")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python parse_burst_throughput_v2.py <absolute_path_to_file>")
        sys.exit(1)
    
    process_bursts(sys.argv[1])