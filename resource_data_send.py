import subprocess
import pandas as pd
import sys
import mysql.connector as mc
import time
import datetime
from time import strftime
from datetime import datetime, date, timezone
import random 
import os
import paramiko
import requests

def convert_to_bytes(value_str):
    """ Convert memory size with units to bytes. """
    try:
        if not value_str:
            raise ValueError("Empty string")
        
        value, unit = value_str[:-2], value_str[-2:]
        if unit not in ['Ki', 'Mi', 'Gi', 'Ti', 'Pi', 'Ei', 'B']:
            unit = 'B'  # Default to bytes if unit not found
        
        value = float(value)
        unit_multipliers = {
            'Ki': 1024,
            'Mi': 1024 ** 2,
            'Gi': 1024 ** 3,
            'Ti': 1024 ** 4,
            'Pi': 1024 ** 5,
            'Ei': 1024 ** 6,
            'B': 1
        }
        return int(value * unit_multipliers.get(unit, 1))  # Default to bytes if unit not found
    except ValueError as e:
        print(f"Error converting '{value_str}': {e}")
        return 0  # Return 0 for invalid values

def get_memory_usage_in_bytes():
    # Run the 'free -h' command and capture the output
    result = subprocess.run(['free', '-h'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')

    # Parse headers and memory line
    headers = lines[0].split()
    mem_values = lines[1].split()[1:]  # Skip the 'Mem:' label
    swap_values = lines[2].split()[1:]  # Skip the 'Swap:' label

    # Determine number of expected memory and swap values
    expected_memory_headers = ['total', 'used', 'free', 'shared', 'buff/cache', 'available']
    expected_swap_headers = ['total', 'used', 'free']

    # Create a dictionary to store the values in bytes
    memory_info = {}

    # Handle memory info
    for i, header in enumerate(expected_memory_headers):
        try:
            value = mem_values[i]
            memory_info[f'Mem_{header}'] = convert_to_bytes(value)
        except IndexError:
            print(f"Missing value for header '{header}'")
            memory_info[f'Mem_{header}'] = 0

    # Handle swap info
    for i, header in enumerate(expected_swap_headers):
        try:
            value = swap_values[i]
            memory_info[f'Swap_{header}'] = convert_to_bytes(value)
        except IndexError:
            print(f"Missing value for header '{header}'")
            memory_info[f'Swap_{header}'] = 0

    return memory_info

def get_cpu_usage():
    # Run the 'mpstat' command and capture the output
    result = subprocess.run(['mpstat', '1', '1'], capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    
    # Extract the CPU usage information
    cpu_usage_line = lines[-1]  # The last line contains the CPU usage stats
    columns = cpu_usage_line.split()
    
    if len(columns) >= 6:
        cpu_usage = {
            'user': float(columns[2]),
            'nice': float(columns[3]),
            'system': float(columns[4]),
            'iowait': float(columns[5]),
            'irq': float(columns[6]),
            'softirq': float(columns[7]),
            'steal': float(columns[8]),
            'idle': float(columns[9])
        }
    else:
        cpu_usage = {
            'user': 0.0,
            'nice': 0.0,
            'system': 0.0,
            'iowait': 0.0,
            'irq': 0.0,
            'softirq': 0.0,
            'steal': 0.0,
            'idle': 0.0
        }

    return cpu_usage

def get_disk_usage():
    # Run the 'df -h' command and capture the output
    result = subprocess.run('df -h | head -n 2', shell=True, capture_output=True, text=True)
    lines = result.stdout.strip().split('\n')
    
    # Skip the header and parse each line
    disk_info = {}
    for line in lines[1:]:
        columns = line.split()
        if len(columns) >= 6:
            filesystem, size, used, available, use_percent, mount_point = columns
            disk_info[mount_point] = {
                'filesystem': filesystem,
                'size': size,
                'used': used,
                'available': available,
                'use_percent': use_percent
            }
        else:
            print(f"Skipping line due to unexpected format: {line}")
    
    return disk_info

def get_load_average():
    # Run the 'uptime' command and capture the output
    result = subprocess.run(['uptime'], capture_output=True, text=True)
    output = result.stdout.strip()

    # Extract the load averages
    load_averages = output.split('load average: ')[-1].split(', ')
    if len(load_averages) >= 3:
        load_average_15m = float(load_averages[2])
    else:
        load_average_15m = 0.0

    return load_average_15m

# Get memory usage in bytes
memory_usage_bytes = get_memory_usage_in_bytes()

# Get CPU usage
cpu_usage = get_cpu_usage()

# Get disk usage
disk_usage = get_disk_usage()

# Get load average
load_average_15m = get_load_average()

# Print the results
for key, value in memory_usage_bytes.items():
    print(f"{key}: {value} bytes")

print("CPU Usage:")
for key, value in cpu_usage.items():
    print(f"{key}: {value}%")

print("Disk Usage:")
for mount_point, stats in disk_usage.items():
    print(f"{mount_point}:")
    for key, value in stats.items():
        print(f"  {key}: {value}")

# Prepare data for POST request
current_utc_time = datetime.now(timezone.utc)
current_utc_timestamp = current_utc_time.timestamp()

token = 'LdOT8hyqj6vhEOgUNrz3'
url = 'https://datahub.suessco.com/api/v1/' + token + '/telemetry'

list_memory_usage_bytes = list(memory_usage_bytes.values())
mem_total = list_memory_usage_bytes[0]
mem_used = list_memory_usage_bytes[1]
mem_available = list_memory_usage_bytes[5]

# Prepare data for POST request
myobj = {
  "ts": current_utc_timestamp * 1000,
  "values": {
    "mem_total": mem_total,
    "mem_used": mem_used,
    "mem_free": mem_available,
    "cpu_user": cpu_usage['user'],
    "cpu_system": cpu_usage['system'],
    "load_average_15m": load_average_15m
  } 
}

# Include disk usage data in POST request
for mount_point, stats in disk_usage.items():
    myobj['values'][f'disk_{mount_point}_size'] = stats['size']
    myobj['values'][f'disk_{mount_point}_used'] = stats['used']
    myobj['values'][f'disk_{mount_point}_available'] = stats['available']
    myobj['values'][f'disk_{mount_point}_use_percent'] = stats['use_percent']

# Send the data to the endpoint
er = requests.post(url, json=myobj)
print(er.text)
print(er.status_code)
