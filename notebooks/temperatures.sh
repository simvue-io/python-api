#!/bin/bash
"""
This file is used to create dummy temperature data for the Non-Python Example.
"""
# Output file
script_dir=$(dirname "$0")
output_file="$script_dir/temperatures.csv"

# Parameters
initial_temp=20
linear_rate=5
decay_rate=0.05
num_linear_steps=10
num_decay_steps=20
time_per_step=5

# Create or clear the output file
echo "Step,Time,Temperature" > $output_file

# Generate linear increase
echo "Sample is being heated"

for ((i=0; i<num_linear_steps; i++)); do
    time=$((i * time_per_step))
    temp=$((initial_temp + i * linear_rate))
    echo "$i,$time,$temp" >> $output_file
    sleep $time_per_step
done

# Generate exponential decay
echo "Sample is cooling"

for ((i=0; i<=num_decay_steps; i++)); do
    step=$((num_linear_steps + i))
    time=$((step * time_per_step))
    temp=$(awk "BEGIN {print $initial_temp + $num_linear_steps * $linear_rate * exp(-$decay_rate * $i)}")
    echo "$step,$time,$temp" >> $output_file
    sleep $time_per_step
done

echo "Temperature data has been written to $output_file"
