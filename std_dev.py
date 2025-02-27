# # import math


# # class OnlineStats:
# #     def __init__(self, threshold=2):  # k=2 for outliers
# #         self.n = 0
# #         self.mean = 0
# #         self.m2 = 0
# #         self.threshold = threshold

# #     def update(self, new_value):
# #         self.n += 1
# #         delta = new_value - self.mean
# #         self.mean += delta / self.n
# #         delta2 = new_value - self.mean
# #         self.m2 += delta * delta2

# #         std_dev = math.sqrt(self.m2 / (self.n - 1)) if self.n > 1 else 0.0

# #         # Check for outliers
# #         if abs(new_value - self.mean) > self.threshold * std_dev:
# #             print(f"🚨 Outlier Detected! Value: {new_value}, Mean: {self.mean:.3f}, Std Dev: {std_dev:.3f}")
# #         else:
# #             print(f"Value: {new_value}, Mean: {self.mean:.3f}, Std Dev: {std_dev:.3f}")

# # # # Simulated real-time data stream
# # # stats = OnlineStats(threshold=2)  # Adjust threshold as needed

# # # streaming_data = [0.5, 0.6, 0.7, 0.58, 0.59, 5.0, 0.61, 0.62, 0.57, 10.0]  # 5.0 and 10.0 are outliers

# # # for value in streaming_data:
# # #     stats.update(value)
# import numpy as np

# class OnlineOutlierDetector:
#     def __init__(self, threshold=3):
#         self.mean = 0
#         self.m2 = 0  # Sum of squares of differences from the mean
#         self.count = 0
#         self.std_dev = 0
#         self.threshold = threshold  # Z-score threshold for outlier detection

#     def update(self, value):
#         """Updates running mean and standard deviation using Welford’s Algorithm"""
#         self.count += 1
#         delta = value - self.mean
#         self.mean += delta / self.count
#         delta2 = value - self.mean
#         self.m2 += delta * delta2

#         if self.count > 1:
#             self.std_dev = np.sqrt(self.m2 / (self.count - 1))  # Sample std dev

#         # Detect outlier using Z-score
#         if self.count > 1 and self.std_dev > 0:
#             z_score = abs((value - self.mean) / self.std_dev)
#             if z_score > self.threshold:
#                 return f"⚠️ Outlier detected: {value} (Z-score: {z_score:.2f})"
        
#         return f"Value: {value}, Mean: {self.mean:.3f}, Std Dev: {self.std_dev:.3f}"

# # Example usage (simulating real-time data logging)
# detector = OnlineOutlierDetector()

# cycle_times = [19.8, 19.85, 19.82, 198.8, 6.94, 5.46, 55.41, 7.74]  # Sample data

# for time_taken in cycle_times:
#     print(detector.update(time_taken))

import numpy as np
from collections import deque
from scipy import stats
window_size = 20
data_window = deque(maxlen=window_size)

def detect_outlier_iqr(value):
    """ Filters outliers using the IQR method before adding to rolling window. """
    
    if len(data_window) < 5:  # Need at least 5 values for meaningful IQR
        data_window.append(value)
        return False  # Not an outlier
    
    q1 = np.percentile(data_window, 25)  # First quartile (Q1)
    q3 = np.percentile(data_window, 75)  # Third quartile (Q3)
    iqr = q3 - q1  # Interquartile Range

    lower_bound = q1 - 1.5 * iqr
    upper_bound = q3 + 1.5 * iqr

    if value < lower_bound or value > upper_bound:
        print(f"⚠️ Outlier detected: {value} (not added)")
        return True  # Outlier detected

    data_window.append(value)  # Add only if not an outlier
    return False




def detect_outlier_zscore(value):
    if len(data_window) < 5:
        data_window.append(value)
        return False  # Not an outlier

    mean = np.mean(data_window)
    std_dev = np.std(data_window)

    if std_dev == 0:
        return False  # Avoid division by zero

    z_score = (value - mean) / std_dev  # Calculate Z-score

    if abs(z_score) > 2.5:  # Adjust threshold (default 3, lower to catch more)
        print(f"⚠️ Outlier detected: {value} (not added)")
        return True  # Outlier detected

    data_window.append(value)
    return False


# Example cycle time data (simulating real-time input)
cycle_times = [19.8, 19.85, 19.82, 198.8, 6.94, 5.46, 55.41, 7.74, 19.9, 20.1]

for cycle_time in cycle_times:
    detect_outlier_iqr(cycle_time)

print("\n✅ Data window after filtering outliers:", list(data_window))
