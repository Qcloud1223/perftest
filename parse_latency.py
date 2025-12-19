import sys
import os
import re
import statistics
import matplotlib.pyplot as plt
import numpy as np

def analyze_latency_metadata(file_path):
    # --- Configuration ---
    TSC_FREQ_GHZ = 2.1
    CYCLES_PER_US = TSC_FREQ_GHZ * 1000
    PERCENTILE_CUTOFF = 0.999  # 99.9%

    # --- 1. Extract Metadata from Filename ---
    filename_only = os.path.basename(file_path)
    
    # Helper regex function
    def extract_val(pattern, text, default="?"):
        match = re.search(pattern, text, re.IGNORECASE)
        return match.group(1) if match else default

    txq   = extract_val(r'txq(\d+)', filename_only)
    cqmod = extract_val(r'cqmod(\d+)', filename_only)
    size  = extract_val(r's(\d+)', filename_only) # Matches 's' followed by digits (e.g., s4096)

    print(f"Processing: {filename_only}")
    print(f"Extracted -> TXQ: {txq}, CQMod: {cqmod}, Size: {size}")

    latencies_us = []
    pending_send_ts = None
    line_number = 0

    # --- 2. Parsing ---
    try:
        with open(file_path, 'r') as f:
            for line in f:
                line_number += 1
                line = line.strip()
                if not line:
                    continue
                try:
                    parts = line.split(',')
                    timestamp = int(parts[0])
                    action = parts[1].strip().upper()
                except (ValueError, IndexError):
                    continue

                if action == 'S':
                    if pending_send_ts is not None:
                        raise RuntimeError(f"Error at line {line_number}: Consecutive 'S'.")
                    pending_send_ts = timestamp
                elif action == 'R':
                    if pending_send_ts is None:
                        raise RuntimeError(f"Error at line {line_number}: 'R' without 'S'.")
                    diff_ticks = timestamp - pending_send_ts
                    latency_us = diff_ticks / CYCLES_PER_US
                    latencies_us.append(latency_us)
                    pending_send_ts = None

        if len(latencies_us) < 2:
            print("Error: Need at least 2 data points.")
            return

    except Exception as e:
        print(f"Analysis Failed: {e}")
        sys.exit(1)

    # --- 3. Statistics & Filtering ---
    latencies_sorted = sorted(latencies_us)
    
    # Filter by P99.9
    p_idx = int(len(latencies_sorted) * PERCENTILE_CUTOFF)
    p_idx = min(p_idx, len(latencies_sorted) - 1)
    cutoff_val = latencies_sorted[p_idx]
    
    filtered_data = [x for x in latencies_us if x <= cutoff_val]
    
    # Basic Stats
    mean_val = statistics.mean(filtered_data)
    median_val = statistics.median(filtered_data)
    min_val = min(filtered_data)
    max_val = max(filtered_data)
    try:
        stdev_val = statistics.stdev(filtered_data)
    except: 
        stdev_val = 0.0

    # QCD Calculation (Robust Deviation Rate)
    q1 = np.percentile(filtered_data, 25)
    q3 = np.percentile(filtered_data, 75)
    
    if (q3 + q1) > 0:
        qcd_val = (q3 - q1) / (q3 + q1)
    else:
        qcd_val = 0.0

    # --- PRINT STATS ---
    print("-" * 40)
    print(f"Original Count:   {len(latencies_us)}")
    print(f"Cutoff (P{PERCENTILE_CUTOFF*100}):  {cutoff_val:.4f} us")
    print("-" * 40)
    print(f"Filtered Min:     {min_val:.4f} us")
    print(f"Filtered Max:     {max_val:.4f} us")
    print(f"Filtered Median:  {median_val:.4f} us")
    print(f"Filtered Mean:    {mean_val:.4f} us")
    print(f"Filtered StdDev:  {stdev_val:.4f} us")
    print(f"Filtered QCD:     {qcd_val:.4f} (Deviation Rate)")
    print("-" * 40)

    # --- 4. Plotting ---
    plt.figure(figsize=(12, 6))

    weights = np.ones_like(filtered_data) / len(filtered_data)

    plt.hist(filtered_data, bins=80, weights=weights,
             color='#4c72b0', edgecolor='white', alpha=0.9)
    
    # Centering logic
    dist_to_max = cutoff_val - median_val
    span = dist_to_max 
    x_min = median_val - span
    x_max = median_val + span
    plt.xlim(x_min, x_max)
    
    plt.axvline(median_val, color='red', linestyle='dashed', linewidth=1.5, 
                label=f'Median ({median_val:.2f}us)')

    # Build Title String
    # e.g., "Size: 4096 | TXQ: 64 | CQMod: 16"
    title_str = f"Size: {size}B | TXQ: {txq} | CQMod: {cqmod}"
    
    plt.title(f'{title_str}\nLatency Hist (First {PERCENTILE_CUTOFF*100}% - Centered Median) | QCD: {qcd_val:.3f}')
    plt.xlabel('Latency (microseconds)')
    plt.ylabel('Probability')
    plt.legend()
    plt.grid(axis='y', linestyle='--', alpha=0.5)

    base_name, _ = os.path.splitext(file_path)
    output_image_path = base_name + ".png"
    plt.savefig(output_image_path)
    print(f"Histogram saved to: {output_image_path}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python latency_metadata.py <absolute_path_to_file>")
        sys.exit(1)
    
    analyze_latency_metadata(sys.argv[1])