import tkinter as tk
from tkinter import filedialog
import pandas as pd
import sys

root = tk.Tk()
root.withdraw()
file_path = filedialog.askopenfilename(title="Select a file", filetypes=[("CSV files", "*.csv"), ("Text files", "*.txt")])

if not file_path:
    sys.exit()
if file_path.endswith('.csv'):
    df = pd.read_csv(file_path)
elif file_path.endswith('.txt'):
    df = pd.read_csv(file_path, delimiter="\t")
else:
    raise ValueError("Unsupported file format. Please provide a .csv or .txt file.")

