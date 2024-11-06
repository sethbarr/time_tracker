import tkinter as tk
from tkinter import ttk, filedialog, messagebox
import json
from pathlib import Path
import pandas as pd
from datetime import datetime, timedelta
import threading
import time
import shutil
import csv
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph
from reportlab.lib.styles import getSampleStyleSheet
import platform
import pyautogui
import matplotlib.pyplot as plt
from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
from pynput import keyboard

class TimeTrackerApp:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Enhanced Time Tracker")
        self.root.geometry("600x800")
        
        # Data storage setup
        self.data_dir = Path.home() / '.timetracker'
        self.data_file = self.data_dir / 'time_data.json'
        self.backup_dir = self.data_dir / 'backups'
        self.data_dir.mkdir(exist_ok=True)
        self.backup_dir.mkdir(exist_ok=True)
        
        # App state
        self.current_project = None
        self.current_category = None
        self.start_time = None
        self.last_activity = time.time()
        self.time_entries = self.load_data()
        
        # Settings
        self.idle_threshold = 300  # 5 minutes default
        self.reminder_interval = 1800  # 30 minutes default
        self.is_paused = False
        self.last_mouse_position = pyautogui.position()
        self.current_keys = set()
        
        # Setup keyboard listener
        self.setup_keyboard_listener()
        
        # Setup GUI
        self.setup_gui()
        
        # Start background tasks
        self.start_background_tasks()
    
    def setup_keyboard_listener(self):
        """Setup global hotkeys using pynput"""
        def on_press(key):
            try:
                # Add key to current keys
                self.current_keys.add(key)
                
                # Check for Command+Option+T (Mac) or Ctrl+Alt+T (Windows/Linux)
                if key == keyboard.Key.tab and (
                    keyboard.Key.cmd in self.current_keys or 
                    keyboard.Key.ctrl in self.current_keys
                ):
                    self.root.after(0, self.toggle_timer)
            except AttributeError:
                pass

        def on_release(key):
            try:
                self.current_keys.remove(key)
            except KeyError:
                pass

        self.keyboard_listener = keyboard.Listener(on_press=on_press, on_release=on_release)
        self.keyboard_listener.start()

    def setup_gui(self):
            # Add this at the beginning of setup_gui method:
    
        # Create menu bar
        menubar = tk.Menu(self.root)
        self.root.config(menu=menubar)
        
        # File menu
        file_menu = tk.Menu(menubar, tearoff=0)
        menubar.add_cascade(label="File", menu=file_menu)
        
        # Add menu items with accelerator keys
        file_menu.add_command(
            label="Start/Stop Timer", 
            command=self.toggle_timer,
            accelerator="Command-T" if platform.system() == "Darwin" else "Ctrl+T"
        )
        file_menu.add_command(
            label="New Project", 
            command=self.new_project_dialog,
            accelerator="Command-N" if platform.system() == "Darwin" else "Ctrl+N"
        )
        file_menu.add_separator()
        file_menu.add_command(label="Exit", command=self.on_closing)
        
        # Bind keyboard shortcuts
        self.root.bind('<Command-t>' if platform.system() == "Darwin" else '<Control-t>', 
                    lambda e: self.toggle_timer())
        self.root.bind('<Command-n>' if platform.system() == "Darwin" else '<Control-n>', 
                    lambda e: self.new_project_dialog())

        # Main container
        self.main_frame = ttk.Frame(self.root)
        self.main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Project and Category Selection
        self.selection_frame = ttk.LabelFrame(self.main_frame, text="Project & Category", padding="5")
        self.selection_frame.pack(fill=tk.X, pady=5)
        
        # Project selection
        ttk.Label(self.selection_frame, text="Project:").grid(row=0, column=0, padx=5)
        self.project_var = tk.StringVar()
        self.project_dropdown = ttk.Combobox(
            self.selection_frame, 
            textvariable=self.project_var
        )
        self.project_dropdown.grid(row=0, column=1, padx=5, sticky='ew')
        
        # Category selection
        ttk.Label(self.selection_frame, text="Category:").grid(row=1, column=0, padx=5)
        self.category_var = tk.StringVar()
        self.category_dropdown = ttk.Combobox(
            self.selection_frame, 
            textvariable=self.category_var
        )
        self.category_dropdown.grid(row=1, column=1, padx=5, sticky='ew')
        
        # Add billable checkbox
        self.billable_var = tk.BooleanVar(value=True)
        billable_frame = ttk.Frame(self.selection_frame)
        billable_frame.grid(row=2, column=0, columnspan=2, pady=5)
        
        ttk.Checkbutton(
            billable_frame,
            text="Billable",
            variable=self.billable_var
        ).pack(side=tk.LEFT, padx=5)
        
        # Add rate entry
        ttk.Label(billable_frame, text="Rate ($/hr):").pack(side=tk.LEFT, padx=5)
        self.rate_var = tk.StringVar(value="0.00")
        ttk.Entry(
            billable_frame,
            textvariable=self.rate_var,
            width=10
        ).pack(side=tk.LEFT, padx=5)
        
        # Timer display
        self.timer_frame = ttk.LabelFrame(self.main_frame, text="Timer", padding="5")
        self.timer_frame.pack(fill=tk.X, pady=5)
        
        self.current_project_label = ttk.Label(
            self.timer_frame,
            text="No project selected",
            font=('Arial', 12)
        )
        self.current_project_label.pack(pady=5)
        
        self.timer_label = ttk.Label(
            self.timer_frame, 
            text="00:00:00", 
            font=('Arial', 24)
        )
        self.timer_label.pack(pady=10)
        
        # Control buttons
        self.button_frame = ttk.Frame(self.main_frame)
        self.button_frame.pack(fill=tk.X, pady=5)
        
        self.start_button = ttk.Button(
            self.button_frame,
            text="Start (⌘T)", #⌥
            command=self.toggle_timer
        )
        self.start_button.pack(side=tk.LEFT, padx=5)
        
        self.new_project_button = ttk.Button(
            self.button_frame,
            text="New Project",
            command=self.new_project_dialog
        )
        self.new_project_button.pack(side=tk.LEFT, padx=5)
        
        # Reports and Summary Frame
        self.reports_frame = ttk.LabelFrame(self.main_frame, text="Reports & Summary", padding="5")
        self.reports_frame.pack(fill=tk.BOTH, expand=True, pady=5)
        
        # Add report buttons
        for report_type in ["Daily", "Weekly", "Monthly"]:
            btn = ttk.Button(
                self.reports_frame,
                text=f"{report_type} Report",
                command=lambda t=report_type: self.generate_report(t.lower())
            )
            btn.pack(fill=tk.X, pady=2, padx=5)
        
        # Add time summary button
        ttk.Button(
            self.reports_frame,
            text="Time Summary",
            command=self.show_time_summary
        ).pack(fill=tk.X, pady=2, padx=5)
        
        self.update_project_list()
        self.update_category_list()

    def apply_settings(self):
        """Apply new settings from the GUI"""
        try:
            self.idle_threshold = int(self.idle_var.get()) * 60
            self.reminder_interval = int(self.reminder_var.get()) * 60
            self.show_message("Settings updated successfully!")
        except ValueError:
            self.show_message("Please enter valid numbers for settings!")

    def check_activity(self):
        """Check for user activity"""
        current_position = pyautogui.position()
        if current_position == self.last_mouse_position:
            if time.time() - self.last_activity > self.idle_threshold and not self.is_paused:
                self.handle_inactivity()
        else:
            self.last_activity = time.time()
            self.last_mouse_position = current_position
            if self.is_paused:
                self.resume_timer()

    def handle_inactivity(self):
        """Handle user inactivity"""
        self.is_paused = True
        self.pause_time = datetime.now()
        self.root.after(0, lambda: messagebox.showinfo(
            "Inactivity Detected",
            "Timer paused due to inactivity. Move mouse or press any key to resume."
        ))

    def resume_timer(self):
        """Resume timer after inactivity"""
        if self.is_paused:
            pause_duration = (datetime.now() - self.pause_time).total_seconds()
            self.start_time = self.start_time + timedelta(seconds=pause_duration)
            self.is_paused = False

    def check_task_reminder(self):
        """Check if it's time to remind user about current task"""
        if self.start_time and not self.is_paused:
            duration = (datetime.now() - self.start_time).total_seconds()
            if duration >= self.reminder_interval and duration % self.reminder_interval < 1:
                self.show_task_reminder()

    def show_task_reminder(self):
        """Show task reminder dialog"""
        if messagebox.askyesno(
            "Task Reminder",
            f"Been working on '{self.project_var.get()}' for "
            f"{int(self.reminder_interval/60)} minutes.\n"
            f"Still working on this task?"
        ):
            # If yes, update the start time for next reminder
            self.last_reminder_time = datetime.now()
        else:
            self.stop_timer()

    def start_background_tasks(self):
        """Start all background monitoring threads"""
        def run_checks():
            while True:
                self.root.after(0, self.check_activity)
                self.root.after(0, self.check_task_reminder)
                time.sleep(1)

        self.monitor_thread = threading.Thread(target=run_checks, daemon=True)
        self.monitor_thread.start()

    def toggle_timer(self):
        """Start or stop the timer"""
        if self.start_time is None:
            if not self.project_var.get():
                self.show_message("Please select a project first!")
                return
            self.start_time = datetime.now()
            self.start_button.config(text="Stop (⌘⌥T)")
            self.current_project_label.config(
                text=f"Current project: {self.project_var.get()}"
            )
            self.update_timer()
        else:
            self.stop_timer()
    def modify_entry(self):
    # Add billable field to time entry
        entry = {
            "project": self.project_var.get(),
            "category": self.category_var.get(),
            "start": self.start_time.isoformat(),
            "end": end_time.isoformat(),
            "duration": duration,
            "billable": self.billable_var.get(),
            "rate": float(self.rate_var.get() or 0)
        }
        return entry

    def update_timer(self):
        """Update the timer display"""
        if self.start_time and not self.is_paused:
            duration = datetime.now() - self.start_time
            hours, remainder = divmod(duration.seconds, 3600)
            minutes, seconds = divmod(remainder, 60)
            self.timer_label.config(
                text=f"{hours:02d}:{minutes:02d}:{seconds:02d}"
            )
            self.root.after(1000, self.update_timer)

    def stop_timer(self):
        """Stop the timer and save the time entry"""
        if self.start_time:
            end_time = datetime.now()
            duration = (end_time - self.start_time).total_seconds()
            
            entry = {
                "project": self.project_var.get(),
                "category": self.category_var.get(),
                "start": self.start_time.isoformat(),
                "end": end_time.isoformat(),
                "duration": duration,
                "billable": self.billable_var.get(),
                "rate": float(self.rate_var.get() or 0)
            }
            
            self.time_entries.append(entry)
            self.save_data()
            
            self.start_time = None
            self.start_button.config(text="Start (⌘⌥T)")
            self.current_project_label.config(text="No project selected")
            self.timer_label.config(text="00:00:00")

    def new_project_dialog(self):
        """Open dialog to create a new project"""
        dialog = tk.Toplevel(self.root)
        dialog.title("New Project")
        dialog.geometry("300x100")
        
        ttk.Label(dialog, text="Project Name:").pack(pady=5)
        entry = ttk.Entry(dialog)
        entry.pack(pady=5)
        
        def save_project():
            project_name = entry.get()
            if project_name:
                self.update_project_list(new_project=project_name)
                dialog.destroy()
        
        ttk.Button(dialog, text="Save", command=save_project).pack(pady=5)

    def update_project_list(self, new_project=None):
        """Update the project dropdown list"""
        projects = set()
        for entry in self.time_entries:
            projects.add(entry['project'])
        if new_project:
            projects.add(new_project)
        self.project_dropdown['values'] = list(projects)
        if new_project:
            self.project_var.set(new_project)

    def update_category_list(self, new_category=None):
        """Update the category dropdown list"""
        categories = set()
        for entry in self.time_entries:
            if 'category' in entry:
                categories.add(entry['category'])
        if new_category:
            categories.add(new_category)
        self.category_dropdown['values'] = list(categories)
        if new_category:
            self.category_var.set(new_category)
    
    def calculate_project_totals(self):
        """Calculate total time and billable amounts per project"""
        df = pd.DataFrame(self.time_entries)
        if df.empty:
            return pd.DataFrame()
        
        # Convert duration to hours
        df['duration'] = df['duration'] / 3600
        
        # Calculate totals by project
        totals = df.groupby('project').agg({
            'duration': 'sum',
            'billable': lambda x: x.sum() if 'billable' in df.columns else len(x)
        }).round(2)
        
        # Calculate billable amounts if rate exists
        if 'rate' in df.columns:
            billable_time = df[df['billable'] == True] if 'billable' in df.columns else df
            billable_amounts = billable_time.groupby('project').apply(
                lambda x: (x['duration'] * x['rate']).sum()
            ).round(2)
            totals['billable_amount'] = billable_amounts
        
        return totals

    def show_time_summary(self):
        """Display time summary window"""
        summary_window = tk.Toplevel(self.root)
        summary_window.title("Time Summary")
        summary_window.geometry("600x400")
        
        # Create treeview
        tree = ttk.Treeview(summary_window)
        tree["columns"] = ("total_hours", "billable_hours", "amount")
        
        # Configure columns
        tree.column("#0", width=120, stretch=tk.YES)
        tree.column("total_hours", width=100, anchor=tk.E)
        tree.column("billable_hours", width=100, anchor=tk.E)
        tree.column("amount", width=100, anchor=tk.E)
        
        # Configure headings
        tree.heading("#0", text="Project")
        tree.heading("total_hours", text="Total Hours")
        tree.heading("billable_hours", text="Billable Hours")
        tree.heading("amount", text="Billable Amount")
        
        # Calculate totals
        totals = self.calculate_project_totals()
        
        # Insert data
        for project, row in totals.iterrows():
            tree.insert("", "end", text=project, values=(
                f"{row['duration']:.2f}",
                f"{row['billable']:.2f}" if 'billable' in row else f"{row['duration']:.2f}",
                f"${row['billable_amount']:.2f}" if 'billable_amount' in row else "$0.00"
            ))
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(summary_window, orient="vertical", command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add export button
        ttk.Button(
            summary_window,
            text="Export Summary",
            command=lambda: self.export_summary(totals)
        ).pack(pady=5)

    def export_summary(self, totals):
        """Export time summary to CSV"""
        file_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=[("CSV files", "*.csv")]
        )
        if file_path:
            totals.to_csv(file_path)
            self.show_message("Summary exported successfully!")

    def load_data(self):
        """Load time entries from JSON file"""
        try:
            if self.data_file.exists():
                with open(self.data_file, 'r') as f:
                    return json.load(f)
        except Exception as e:
            self.show_message(f"Error loading data: {str(e)}")
        return []

    def save_data(self):
        """Save time entries to JSON file"""
        try:
            with open(self.data_file, 'w') as f:
                json.dump(self.time_entries, f)
        except Exception as e:
            self.show_message(f"Error saving data: {str(e)}")

    def show_message(self, message):
        """Show a message box with the given message"""
        messagebox.showinfo("Time Tracker", message)
        
    def generate_report(self, report_type):
        """Generate enhanced report with plots"""
        df = pd.DataFrame(self.time_entries)
        if df.empty:
            self.show_message("No data available for report!")
            return
            
        df['start'] = pd.to_datetime(df['start'])
        df['duration'] = df['duration'] / 3600  # Convert to hours
        
        report_window = tk.Toplevel(self.root)
        report_window.title(f"{report_type.capitalize()} Report")
        report_window.geometry("800x600")
        
        # Create notebook for different views
        notebook = ttk.Notebook(report_window)
        notebook.pack(fill=tk.BOTH, expand=True)
        
        # Summary tab
        summary_frame = ttk.Frame(notebook)
        notebook.add(summary_frame, text="Summary")
        
        # Project distribution pie chart and daily hours bar chart
        fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 5))
        
        # Filter data based on report type
        today = datetime.now()
        if report_type == 'daily':
            start_date = today.replace(hour=0, minute=0, second=0, microsecond=0)
            df = df[df['start'] >= start_date]
            title_suffix = "Today"
        elif report_type == 'weekly':
            start_date = today - timedelta(days=today.weekday())
            df = df[df['start'] >= start_date]
            title_suffix = "This Week"
        else:  # monthly
            start_date = today.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
            df = df[df['start'] >= start_date]
            title_suffix = "This Month"

        if not df.empty:
            # Project distribution pie chart
            project_data = df.groupby('project')['duration'].sum()
            ax1.pie(project_data, labels=project_data.index, autopct='%1.1f%%')
            ax1.set_title(f'Time Distribution by Project - {title_suffix}')
            
            # Daily hours bar chart
            daily_data = df.groupby(df['start'].dt.date)['duration'].sum()
            ax2.bar(daily_data.index, daily_data.values)
            ax2.set_title(f'Daily Hours - {title_suffix}')
            ax2.tick_params(axis='x', rotation=45)
        else:
            ax1.text(0.5, 0.5, 'No data for this period', ha='center')
            ax2.text(0.5, 0.5, 'No data for this period', ha='center')

        # Adjust layout and display charts
        plt.tight_layout()
        canvas = FigureCanvasTkAgg(fig, summary_frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        
        # Detailed data tab
        data_frame = ttk.Frame(notebook)
        notebook.add(data_frame, text="Detailed Data")
        
        # Create treeview for detailed data
        tree = ttk.Treeview(data_frame)
        tree["columns"] = ("project", "category", "start", "duration")
        
        # Configure columns
        tree.column("#0", width=0, stretch=tk.NO)
        tree.column("project", anchor=tk.W, width=120)
        tree.column("category", anchor=tk.W, width=120)
        tree.column("start", anchor=tk.W, width=160)
        tree.column("duration", anchor=tk.E, width=100)
        
        # Configure headings
        tree.heading("project", text="Project", anchor=tk.W)
        tree.heading("category", text="Category", anchor=tk.W)
        tree.heading("start", text="Start Time", anchor=tk.W)
        tree.heading("duration", text="Hours", anchor=tk.E)
        
        # Add scrollbar
        scrollbar = ttk.Scrollbar(data_frame, orient="vertical", command=tree.yview)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        tree.configure(yscrollcommand=scrollbar.set)
        
        # Populate treeview
        for _, row in df.iterrows():
            tree.insert("", "end", values=(
                row['project'],
                row.get('category', ''),
                row['start'].strftime('%Y-%m-%d %H:%M'),
                f"{row['duration']:.2f}"
            ))
        
        tree.pack(fill=tk.BOTH, expand=True, padx=5, pady=5)
        
        # Add export buttons
        export_frame = ttk.Frame(report_window)
        export_frame.pack(fill=tk.X, padx=5, pady=5)
        
        ttk.Button(
            export_frame,
            text="Export to CSV",
            command=lambda: self.export_data(df, 'csv')
        ).pack(side=tk.LEFT, padx=5)
        
        ttk.Button(
            export_frame,
            text="Export to PDF",
            command=lambda: self.export_data(df, 'pdf')
        ).pack(side=tk.LEFT, padx=5)

    def export_data(self, df, format_type):
        """Export report data to CSV or PDF"""
        if format_type == 'csv':
            file_path = filedialog.asksaveasfilename(
                defaultextension=".csv",
                filetypes=[("CSV files", "*.csv")]
            )
            if file_path:
                df.to_csv(file_path, index=False)
                self.show_message("Data exported to CSV successfully!")
        else:  # PDF
            file_path = filedialog.asksaveasfilename(
                defaultextension=".pdf",
                filetypes=[("PDF files", "*.pdf")]
            )
            if file_path:
                doc = SimpleDocTemplate(file_path, pagesize=letter)
                styles = getSampleStyleSheet()
                elements = []
                
                # Add title
                elements.append(Paragraph("Time Tracking Report", styles['Title']))
                elements.append(Paragraph(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M')}", styles['Normal']))
                
                # Convert data to table format
                table_data = [['Project', 'Category', 'Start Time', 'Duration (hours)']]
                for _, row in df.iterrows():
                    table_data.append([
                        row['project'],
                        row.get('category', ''),
                        row['start'].strftime('%Y-%m-%d %H:%M'),
                        f"{row['duration']:.2f}"
                    ])
                
                # Create and style the table
                t = Table(table_data)
                t.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (-1, 0), colors.grey),
                    ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, 0), 14),
                    ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
                    ('BACKGROUND', (0, 1), (-1, -1), colors.white),
                    ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
                    ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
                    ('FONTSIZE', (0, 1), (-1, -1), 12),
                    ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
                    ('GRID', (0, 0), (-1, -1), 1, colors.black)
                ]))
                elements.append(t)
                
                try:
                    doc.build(elements)
                    self.show_message("Data exported to PDF successfully!")
                except Exception as e:
                    self.show_message(f"Error exporting to PDF: {str(e)}")

    def run(self):
        """Start the application main loop"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
    
    def on_closing(self):
        """Handle application closing"""
        if self.start_time:
            self.stop_timer()
        self.root.destroy()

if __name__ == "__main__":
    app = TimeTrackerApp()
    app.run()