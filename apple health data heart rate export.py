import xml.etree.ElementTree as ET
import csv
from datetime import datetime, timezone
import statistics # For stdev and mean

# Attempt to import matplotlib for plotting
try:
    import matplotlib.pyplot as plt
    import matplotlib.dates as mdates
    MATPLOTLIB_AVAILABLE = True
except ImportError:
    MATPLOTLIB_AVAILABLE = False
    # This warning will be printed when the script starts if matplotlib is missing
    # print("Warning: Matplotlib is not installed. Plot generation will be skipped. To install: pip install matplotlib")


def parse_cda_datetime(dt_str):
    """
    Parses HL7 CDA datetime string like '20230524020000+0200'
    into a timezone-aware datetime object.
    """
    try:
        return datetime.strptime(dt_str, "%Y%m%d%H%M%S%z")
    except ValueError as e:
        print(f"Warning: Could not parse date string '{dt_str}': {e}. Skipping this record.")
        return None

def get_user_inputs():
    """
    Gets the XML file path, and start and end datetimes from the user.
    User inputs for datetime are assumed to be in their local timezone and are converted to UTC.
    """
    xml_file_path = input("Enter the path to the XML file: ")
    start_dt_str = input("Enter the start date and time (YYYY-MM-DD HH:MM:SS): ")
    end_dt_str = input("Enter the end date and time (YYYY-MM-DD HH:MM:SS): ")
    output_csv_path = "heartrate_data.csv"

    try:
        naive_start_dt = datetime.strptime(start_dt_str, "%Y-%m-%d %H:%M:%S")
        naive_end_dt = datetime.strptime(end_dt_str, "%Y-%m-%d %H:%M:%S")

        start_dt_utc = naive_start_dt.astimezone().astimezone(timezone.utc)
        end_dt_utc = naive_end_dt.astimezone().astimezone(timezone.utc)

    except ValueError:
        print("Invalid date/time format. Please use YYYY-MM-DD HH:MM:SS.")
        return None, None, None, None
    except Exception as e:
        print(f"An error occurred during input processing: {e}")
        return None, None, None, None

    return xml_file_path, start_dt_utc, end_dt_utc, output_csv_path

def extract_heartrate_data(xml_file_path, start_dt_utc, end_dt_utc):
    """
    Parses the CDA XML file, extracts heart rate data within the given time frame.
    Aggregates multiple heart rate values for the same timestamp.
    Returns a dictionary: {datetime_obj: [hr_value1_str, hr_value2_str, ...]}
    """
    processed_records = {} 
    namespaces = {'hl7': 'urn:hl7-org:v3'}

    try:
        tree = ET.parse(xml_file_path)
        root = tree.getroot()
    except FileNotFoundError:
        print(f"Error: XML file not found at {xml_file_path}")
        return {}
    except ET.ParseError as e:
        print(f"Error: Could not parse XML file {xml_file_path}. Details: {e}")
        return {}
    except Exception as e:
        print(f"An unexpected error occurred while parsing the XML file: {e}")
        return {}

    all_observations = root.findall('.//hl7:observation', namespaces)
    
    for obs_node in all_observations:
        code_element = obs_node.find('./hl7:code[@code="8867-4"]', namespaces)
        if code_element is not None: 
            effective_time_low_element = obs_node.find('./hl7:effectiveTime/hl7:low[@value]', namespaces)
            
            dt_str = None
            if effective_time_low_element is not None:
                dt_str = effective_time_low_element.get('value')
            else:
                effective_time_direct_element = obs_node.find('./hl7:effectiveTime[@value]', namespaces)
                if effective_time_direct_element is not None:
                    dt_str = effective_time_direct_element.get('value')
            
            if dt_str is None:
                continue 

            record_dt_aware = parse_cda_datetime(dt_str)
            if record_dt_aware is None:
                continue

            record_dt_utc = record_dt_aware.astimezone(timezone.utc)

            if start_dt_utc <= record_dt_utc <= end_dt_utc:
                value_element = obs_node.find('./hl7:value[@value]', namespaces)
                if value_element is not None:
                    hr_value_str = value_element.get('value')
                    
                    if record_dt_aware not in processed_records:
                        processed_records[record_dt_aware] = []
                    processed_records[record_dt_aware].append(hr_value_str)
    
    return processed_records

def write_to_csv(data_rows, csv_file_path):
    """Writes the extracted data rows to a CSV file."""
    if not data_rows:
        print("No data (where both A and B values are present) to write to CSV.")
        return

    fieldnames = ['date', 'time', 'heartrate_A', 'heartrate_B']
    try:
        with open(csv_file_path, 'w', newline='') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            for row in data_rows:
                writer.writerow(row)
        print(f"Data successfully written to {csv_file_path}")
    except IOError:
        print(f"Error: Could not write to CSV file {csv_file_path}")
    except Exception as e:
        print(f"An unexpected error occurred while writing to CSV: {e}")

def generate_plot(timestamps, series_a, series_b, plot_filename="heartrate_plot.png"):
    """Generates and saves a time series plot of heart rate data."""
    if not MATPLOTLIB_AVAILABLE:
        print("Matplotlib not available. Skipping plot generation.")
        return

    if not timestamps: 
        print("No data points where both Heartrate A and B have values. Plot will not be generated.")
        return
    
    if not (any(v is not None for v in series_a) and any(v is not None for v in series_b)):
         print("No plottable numerical data for Series A and B after filtering/conversion. Plot will not be generated.")
         return

    fig, ax = plt.subplots(figsize=(15, 7))

    ax.plot(timestamps, series_a, label='Heart Rate A', marker='.', linestyle='-', markersize=4)
    ax.plot(timestamps, series_b, label='Heart Rate B', marker='.', linestyle='-', markersize=4, alpha=0.7)

    ax.set_xlabel("Time")
    ax.set_ylabel("Heart Rate (bpm)")
    ax.set_title("Heart Rate Over Time (timestamps with both A & B values)")
    
    ax.legend()

    ax.xaxis.set_major_formatter(mdates.DateFormatter('%Y-%m-%d %H:%M'))
    fig.autofmt_xdate(rotation=45)
    plt.grid(True, which='both', linestyle='--', linewidth=0.5)
    plt.tight_layout()

    try:
        plt.savefig(plot_filename)
        print(f"Plot saved to {plot_filename}")
    except Exception as e:
        print(f"Error saving plot: {e}")

def main():
    """Main function to orchestrate the extraction, CSV generation, and plotting."""
    if not MATPLOTLIB_AVAILABLE:
         print("Warning: Matplotlib is not installed. Plot generation will be skipped. To install: pip install matplotlib")

    xml_file_path, start_dt_utc, end_dt_utc, output_csv_path = get_user_inputs()

    if not all([xml_file_path, start_dt_utc, end_dt_utc, output_csv_path]):
        print("Input acquisition failed or was incomplete. Exiting.")
        return

    print(f"\nProcessing XML file: {xml_file_path}")
    start_time_str = start_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z') if start_dt_utc else "N/A"
    end_time_str = end_dt_utc.strftime('%Y-%m-%d %H:%M:%S %Z') if end_dt_utc else "N/A"
    print(f"Extracting data from {start_time_str} to {end_time_str} (times in UTC for comparison)")

    processed_records = extract_heartrate_data(xml_file_path, start_dt_utc, end_dt_utc)

    if not processed_records:
        print("No heart rate data found in the XML for the specified timeframe.")
        return

    csv_output_rows = []
    plot_timestamps = []
    plot_series_a_values = [] # Stores floats or Nones
    plot_series_b_values = [] # Stores floats or Nones
    percentage_differences = [] # Stores float percentages

    sorted_timestamps = sorted(processed_records.keys())

    for ts_aware in sorted_timestamps:
        hr_values_str_list = processed_records[ts_aware]
        
        if len(hr_values_str_list) >= 2: # Filter: only include if at least two values
            date_str = ts_aware.strftime('%Y-%m-%d')
            time_str = ts_aware.strftime('%H:%M:%S')
            
            hr_a_str = hr_values_str_list[0] 
            hr_b_str = hr_values_str_list[1]
            
            if len(hr_values_str_list) > 2:
                print(f"Warning: Timestamp {ts_aware.strftime('%Y-%m-%d %H:%M:%S %Z')} has {len(hr_values_str_list)} heart rate values. CSV/Plot will use the first two.")

            csv_output_rows.append({
                'date': date_str,
                'time': time_str,
                'heartrate_A': hr_a_str,
                'heartrate_B': hr_b_str
            })
            
            val_a_num, val_b_num = None, None
            try:
                val_a_num = float(hr_a_str)
            except ValueError:
                print(f"Warning: Could not convert heartrate_A value '{hr_a_str}' to float at {ts_aware.strftime('%Y-%m-%d %H:%M:%S %Z')}.")
            try:
                val_b_num = float(hr_b_str)
            except ValueError:
                print(f"Warning: Could not convert heartrate_B value '{hr_b_str}' to float at {ts_aware.strftime('%Y-%m-%d %H:%M:%S %Z')}.")

            plot_timestamps.append(ts_aware)
            plot_series_a_values.append(val_a_num)
            plot_series_b_values.append(val_b_num)

            if val_a_num is not None and val_b_num is not None:
                denominator = (val_a_num + val_b_num) / 2
                if denominator != 0:
                    diff_p = (abs(val_a_num - val_b_num) / denominator) * 100
                    percentage_differences.append(diff_p)
                elif val_a_num == 0 and val_b_num == 0:
                    percentage_differences.append(0.0)

    if csv_output_rows:
        write_to_csv(csv_output_rows, output_csv_path)
    else:
        print("No heart rate data found where both A and B values are present for the same timestamp within the selected range.")
    
    print("\n--- Statistical Summary ---")
    # Calculate Standard Deviations
    valid_series_a_for_stdev = [v for v in plot_series_a_values if v is not None]
    valid_series_b_for_stdev = [v for v in plot_series_b_values if v is not None]

    if len(valid_series_a_for_stdev) >= 2:
        stdev_a = statistics.stdev(valid_series_a_for_stdev)
        print(f"Standard Deviation for Heart Rate A: {stdev_a:.2f} bpm (based on {len(valid_series_a_for_stdev)} plotted points)")
    else:
        print("Not enough data points (>=2) for Heart Rate A to calculate standard deviation.")

    if len(valid_series_b_for_stdev) >= 2:
        stdev_b = statistics.stdev(valid_series_b_for_stdev)
        print(f"Standard Deviation for Heart Rate B: {stdev_b:.2f} bpm (based on {len(valid_series_b_for_stdev)} plotted points)")
    else:
        print("Not enough data points (>=2) for Heart Rate B to calculate standard deviation.")

    # Calculate Average Percentage Difference
    if percentage_differences:
        avg_percentage_diff = statistics.mean(percentage_differences)
        print(f"Average Percentage Difference between A and B: {avg_percentage_diff:.2f}% (based on {len(percentage_differences)} paired measurements)")
    else:
        print("No valid paired measurements (where both A and B are numeric) to calculate average percentage difference.")
    print("-------------------------\n")

    if plot_timestamps:
        generate_plot(plot_timestamps, plot_series_a_values, plot_series_b_values)
    else:
        print("No data points to plot (requires both A and B values per timestamp).")

if __name__ == "__main__":
    main()
