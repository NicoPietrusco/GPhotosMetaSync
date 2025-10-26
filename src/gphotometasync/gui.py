"""
Desktop GUI for GPhotoMetaSync using Tkinter.

This provides a simple desktop application for users who prefer
graphical interfaces over command line tools.
"""

import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, scrolledtext, ttk
from typing import List

from .settings import settings
from .utils.logger_utils import setup_logger

# Setup logger
setup_logger()


class GPhotoMetaSyncGUI:
    """Main desktop application window."""

    def __init__(self):
        """Initialize the GUI application."""
        self.root = tk.Tk()
        self.root.title(f"{settings.APP_NAME} v{settings.APP_VERSION}")
        self.root.geometry("950x750")
        self.root.minsize(900, 700)

        # Application state
        self.selected_files = []
        self.processing_thread = None
        self.log_messages = []
        self.message_queue = queue.Queue()

        # Style configuration
        self.setup_styles()
        self.create_ui()
        self.update_ui_state()

        # Start message processing
        self.process_queue()

    def process_queue(self):
        """Process messages from the worker thread."""
        try:
            while True:
                message_type, data = self.message_queue.get_nowait()
                if message_type == "progress":
                    self.update_progress(data[0], data[1])
                elif message_type == "finished":
                    self.processing_finished(data[0], data[1])
                elif message_type == "log":
                    self.add_log_message(data)
        except queue.Empty:
            pass

        # Schedule next check
        self.root.after(100, self.process_queue)

    def setup_styles(self):
        """Setup ttk styles for better appearance."""
        style = ttk.Style()

        # Configure modern button style
        style.configure("Action.TButton", font=("Helvetica", 10, "bold"), padding=10)

        # Configure progress bar
        style.configure(
            "Custom.Horizontal.TProgressbar",
            background="#007bff",
            troughcolor="#e9ecef",
            borderwidth=0,
            lightcolor="#007bff",
            darkcolor="#007bff",
        )

    def create_ui(self):
        """Create the user interface."""
        # Main container
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Configure grid weights
        self.root.columnconfigure(0, weight=1)
        self.root.rowconfigure(0, weight=1)
        main_frame.columnconfigure(0, weight=1)
        main_frame.columnconfigure(1, weight=1)
        main_frame.rowconfigure(5, weight=1)  # Results section can expand

        # Header
        self.create_header(main_frame)

        # File selection section
        self.create_file_section(main_frame)

        # Options section
        self.create_options_section(main_frame)

        # Action buttons
        self.create_action_buttons(main_frame)

        # Progress section
        self.create_progress_section(main_frame)

        # Results section
        self.create_results_section(main_frame)

        # Status bar
        self.status_var = tk.StringVar(value="Ready")
        status_bar = ttk.Label(
            self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W
        )
        status_bar.grid(row=1, column=0, sticky=(tk.W, tk.E))

    def create_header(self, parent):
        """Create the application header."""
        header_frame = ttk.LabelFrame(parent, text="📸 GPhotoMetaSync", padding="10")
        header_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        header_frame.columnconfigure(0, weight=1)

        title_label = ttk.Label(
            header_frame,
            text=f"Google Photos Metadata Synchronizer v{settings.APP_VERSION}",
            font=("Helvetica", 12, "bold"),
        )
        title_label.grid(row=0, column=0, sticky=tk.W)

        desc_label = ttk.Label(
            header_frame,
            text="Extract EXIF data from images or embed original dates",
            foreground="#666",
        )
        desc_label.grid(row=1, column=0, sticky=tk.W, pady=(5, 0))

    def create_file_section(self, parent):
        """Create the file selection section."""
        file_frame = ttk.LabelFrame(parent, text="📁 File Selection", padding="10")
        file_frame.grid(
            row=1, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10)
        )
        file_frame.columnconfigure(0, weight=1)
        file_frame.rowconfigure(0, weight=1)

        # File list
        list_frame = ttk.Frame(file_frame)
        list_frame.grid(row=0, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        list_frame.columnconfigure(0, weight=1)

        # Treeview for file list
        columns = ("name", "size", "path")
        self.file_tree = ttk.Treeview(list_frame, columns=columns, show="headings", height=4)
        self.file_tree.heading("name", text="File Name")
        self.file_tree.heading("size", text="Size")
        self.file_tree.heading("path", text="Path")
        self.file_tree.column("name", width=200)
        self.file_tree.column("size", width=100)
        self.file_tree.column("path", width=300)

        # Scrollbar for treeview
        tree_scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.file_tree.yview)
        self.file_tree.configure(yscrollcommand=tree_scrollbar.set)

        self.file_tree.grid(row=0, column=0, sticky=(tk.W, tk.E))
        tree_scrollbar.grid(row=0, column=1, sticky=(tk.N, tk.S))

        list_frame.columnconfigure(0, weight=1)

        # File selection buttons
        button_frame = ttk.Frame(file_frame)
        button_frame.grid(row=1, column=0, columnspan=2, pady=(5, 0), sticky=tk.W)

        select_files_btn = ttk.Button(
            button_frame,
            text="📂 Select Files",
            command=self.select_files,
            style="Action.TButton",
            cursor="hand2",
        )
        select_files_btn.grid(row=0, column=0, padx=(0, 10))

        select_dir_btn = ttk.Button(
            button_frame,
            text="📁 Select Directory",
            command=self.select_directory,
            style="Action.TButton",
            cursor="hand2",
        )
        select_dir_btn.grid(row=0, column=1, padx=(0, 10))

        clear_btn = ttk.Button(
            button_frame, text="🗑️ Clear", command=self.clear_files, cursor="hand2"
        )
        clear_btn.grid(row=0, column=2)

    def create_options_section(self, parent):
        """Create the options section."""
        options_frame = ttk.LabelFrame(parent, text="⚙️ Options", padding="10")
        options_frame.grid(row=2, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))
        options_frame.columnconfigure(1, weight=1)

        # Output directory
        ttk.Label(options_frame, text="Output Directory:").grid(
            row=0, column=0, sticky=tk.W, pady=5
        )

        self.output_dir_var = tk.StringVar(value="output")
        output_entry = ttk.Entry(options_frame, textvariable=self.output_dir_var, width=40)
        output_entry.grid(row=0, column=1, sticky=(tk.W, tk.E), pady=5, padx=(10, 5))

        browse_btn = ttk.Button(
            options_frame, text="📁 Browse", command=self.select_output_directory, cursor="hand2"
        )
        browse_btn.grid(row=0, column=2, pady=5)

        # Verbose option
        self.verbose_var = tk.BooleanVar(value=False)
        verbose_check = ttk.Checkbutton(
            options_frame, text="Show detailed progress information", variable=self.verbose_var
        )
        verbose_check.grid(row=1, column=0, columnspan=3, sticky=tk.W, pady=5)

    def create_action_buttons(self, parent):
        """Create the action buttons."""
        button_frame = ttk.Frame(parent)
        button_frame.grid(row=3, column=0, columnspan=2, pady=(0, 10))

        self.extract_btn = ttk.Button(
            button_frame,
            text="📊 Extract EXIF Data",
            command=lambda: self.start_processing("extract"),
            style="Action.TButton",
            cursor="hand2",
        )
        self.extract_btn.grid(row=0, column=0, padx=(0, 10))

        self.embed_btn = ttk.Button(
            button_frame,
            text="📅 Embed EXIF Dates",
            command=lambda: self.start_processing("embed"),
            style="Action.TButton",
            cursor="hand2",
        )
        self.embed_btn.grid(row=0, column=1)

    def create_progress_section(self, parent):
        """Create the progress section."""
        progress_frame = ttk.LabelFrame(parent, text="📈 Progress", padding="10")
        progress_frame.grid(row=4, column=0, columnspan=2, sticky=(tk.W, tk.E), pady=(0, 10))

        # Progress bar
        self.progress_var = tk.DoubleVar()
        self.progress_bar = ttk.Progressbar(
            progress_frame,
            variable=self.progress_var,
            maximum=100,
            style="Custom.Horizontal.TProgressbar",
        )
        self.progress_bar.grid(row=0, column=0, sticky=(tk.W, tk.E), pady=(0, 5))

        # Progress label
        self.progress_label_var = tk.StringVar(value="Ready to process...")
        progress_label = ttk.Label(progress_frame, textvariable=self.progress_label_var)
        progress_label.grid(row=1, column=0, sticky=tk.W)

    def create_results_section(self, parent):
        """Create the results section."""
        results_frame = ttk.LabelFrame(parent, text="📋 Results", padding="10")
        results_frame.grid(
            row=5, column=0, columnspan=2, sticky=(tk.W, tk.E, tk.N, tk.S), pady=(0, 10)
        )
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        # Notebook for tabs
        self.notebook = ttk.Notebook(results_frame)
        self.notebook.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))

        # Log tab
        log_frame = ttk.Frame(self.notebook)
        self.notebook.add(log_frame, text="📝 Log")

        self.log_text = scrolledtext.ScrolledText(log_frame, height=10, font=("Monospace", 9))
        self.log_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)

        # Summary tab
        summary_frame = ttk.Frame(self.notebook)
        self.notebook.add(summary_frame, text="📊 Summary")

        self.summary_text = scrolledtext.ScrolledText(summary_frame, height=10)
        self.summary_text.grid(row=0, column=0, sticky=(tk.W, tk.E, tk.N, tk.S))
        summary_frame.columnconfigure(0, weight=1)
        summary_frame.rowconfigure(0, weight=1)

        # Clear button
        clear_btn = ttk.Button(
            results_frame, text="🗑️ Clear Results", command=self.clear_results, cursor="hand2"
        )
        clear_btn.grid(row=1, column=0, pady=(10, 0), sticky=tk.W)

    def select_files(self):
        """Select individual image files."""
        filetypes = [
            (
                f"Image files ({' '.join(f'*{ext}' for ext in settings.SUPPORTED_FORMATS)})",
                " ".join(f"*{ext}" for ext in settings.SUPPORTED_FORMATS),
            ),
            ("All files", "*"),
        ]

        files = filedialog.askopenfilenames(title="Select Image Files", filetypes=filetypes)

        if files:
            self.add_files([Path(f) for f in files])

    def select_directory(self):
        """Select a directory containing images."""
        directory = filedialog.askdirectory(title="Select Input Directory")

        if directory:
            directory_path = Path(directory)

            # Find all image files in directory
            from .utils.file_utils import find_images

            image_files = find_images([directory_path])

            if image_files:
                self.add_files(image_files)
            else:
                messagebox.showwarning(
                    "No Images Found",
                    f"No supported image files found in '{directory}'.\n\n"
                    f"Supported formats: {', '.join(settings.SUPPORTED_FORMATS)}",
                )

    def select_output_directory(self):
        """Select output directory for processed files."""
        directory = filedialog.askdirectory(
            title="Select Output Directory",
            initialdir=self.output_dir_var.get()
            if Path(self.output_dir_var.get()).exists()
            else ".",
        )

        if directory:
            self.output_dir_var.set(directory)
            self.status_var.set(f"Output directory: {directory}")

    def add_files(self, files: List[Path]):
        """Add files to the selection."""
        for file in files:
            if file not in self.selected_files:
                self.selected_files.append(file)

        self.update_file_list()
        self.update_ui_state()

    def clear_files(self):
        """Clear all selected files."""
        self.selected_files.clear()
        self.update_file_list()
        self.update_ui_state()

    def update_file_list(self):
        """Update the file list display."""
        # Clear existing items
        for item in self.file_tree.get_children():
            self.file_tree.delete(item)

        # Add files
        for file in self.selected_files:
            size_mb = file.stat().st_size / (1024 * 1024)
            self.file_tree.insert(
                "", tk.END, values=(file.name, f"{size_mb:.2f} MB", str(file.parent))
            )

        # Update status
        self.status_var.set(f"{len(self.selected_files)} files selected")

    def update_ui_state(self):
        """Update UI element states based on current selection."""
        has_files = len(self.selected_files) > 0
        self.extract_btn.state(["!disabled"] if has_files else ["disabled"])
        self.embed_btn.state(["!disabled"] if has_files else ["disabled"])

    def clear_results(self):
        """Clear the results display."""
        self.log_text.delete(1.0, tk.END)
        self.summary_text.delete(1.0, tk.END)
        self.progress_var.set(0)
        self.progress_label_var.set("Ready to process...")
        self.log_messages.clear()

    def start_processing(self, action: str):
        """Start the processing operation."""
        if not self.selected_files:
            messagebox.showwarning("No Files", "Please select some image files first.")
            return

        # Disable buttons during processing
        self.extract_btn.state(["disabled"])
        self.embed_btn.state(["disabled"])

        # Clear previous results
        self.clear_results()

        # Create and start processing thread
        self.processing_thread = ProcessingThread(
            self.selected_files,
            self.output_dir_var.get(),
            action,
            self.verbose_var.get(),
            self.message_queue,
        )

        # Start processing
        self.processing_thread.start()

    def update_progress(self, value: int, text: str):
        """Update progress bar and label."""
        self.progress_var.set(value)
        self.progress_label_var.set(text)

    def processing_finished(self, message: str, success: bool):
        """Handle processing completion."""
        # Enable buttons
        self.extract_btn.state(["!disabled"])
        self.embed_btn.state(["!disabled"])

        # Update status
        self.status_var.set("Processing complete")

        # Show results
        self.summary_text.insert(tk.END, message)

        # Show success/error message
        if success:
            messagebox.showinfo("Success", message)
        else:
            messagebox.showerror("Error", message)

    def add_log_message(self, message: str):
        """Add a message to the log."""
        self.log_messages.append(message)
        self.log_text.insert(tk.END, message + "\n")
        self.log_text.see(tk.END)  # Scroll to bottom

    def run(self):
        """Run the GUI application."""
        self.root.mainloop()


class ProcessingThread(threading.Thread):
    """Thread for processing images in the background."""

    def __init__(self, files, output_dir, action, verbose=False, message_queue=None):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.action = action
        self.verbose = verbose
        self.message_queue = message_queue

        # Import here to avoid circular imports
        from .utils.logger_utils import get_logger

        self.logger = get_logger(__name__)

    def run(self):
        """Run the processing in a separate thread."""
        try:
            # Send initial progress and log
            self.message_queue.put(("progress", (10, f"Starting {self.action} process...")))
            self.message_queue.put(
                ("log", f"🚀 Starting {self.action} for {len(self.files)} file(s)")
            )
            self.message_queue.put(("log", f"📂 Output directory: {self.output_dir}"))

            if self.action == "extract":
                self.message_queue.put(("log", "📊 Extracting EXIF data..."))
                success_count, failed_files = self._process_extract()
                message = self._build_summary_message(
                    "extract", success_count, len(self.files), failed_files
                )
                success = success_count > 0

            elif self.action == "embed":
                self.message_queue.put(("log", "📅 Embedding EXIF dates..."))
                success_count, failed_files = self._process_embed()
                message = self._build_summary_message(
                    "embed", success_count, len(self.files), failed_files
                )
                success = success_count > 0

            else:
                raise ValueError(f"Unknown action: {self.action}")

            # Send completion message
            self.message_queue.put(("log", message.split("\n")[0]))  # First line to log
            self.message_queue.put(("finished", (message, success)))

        except Exception as e:
            error_msg = f"❌ Processing failed: {str(e)}"
            self.logger.error(error_msg)
            self.message_queue.put(("log", error_msg))
            self.message_queue.put(("finished", (error_msg, False)))

    def _build_summary_message(self, action, success_count, total, failed_files):
        """Build a comprehensive summary message."""
        action_text = (
            "extracted EXIF data from" if action == "extract" else "embedded EXIF dates for"
        )

        message = f"✅ Successfully {action_text} {success_count}/{total} images\n"
        message += "\n📊 Processing Summary:\n"
        message += f"   • Total files: {total}\n"
        message += f"   • Successful: {success_count}\n"
        message += f"   • Failed: {len(failed_files)}\n"

        if failed_files:
            message += "\n⚠️  Failed Images:\n"
            for filename in failed_files:
                message += f"   • {filename}\n"

        message += f"\n📂 Output location: {self.output_dir}"

        return message

    def _process_extract(self):
        """Process files for EXIF extraction with progress updates."""
        from pathlib import Path

        from .core.exif_utils import extract_exif_data

        total = len(self.files)
        success_count = 0
        failed_files = []

        for i, img_path in enumerate(self.files, 1):
            # Update progress
            progress = int(10 + (80 * i / total))
            self.message_queue.put(
                ("progress", (progress, f"Processing {i}/{total}: {img_path.name}"))
            )

            # Log current file
            self.message_queue.put(("log", f"  [{i}/{total}] Processing: {img_path.name}"))

            # Extract EXIF
            result = extract_exif_data(img_path, Path(self.output_dir))

            if "error" in result:
                self.message_queue.put(("log", f"    ❌ Error: {result['error']}"))
                failed_files.append(img_path.name)
            else:
                success_count += 1
                if self.verbose:
                    self.message_queue.put(
                        ("log", f"    ✅ Extracted {result['exif_fields_count']} fields")
                    )

        # Final progress
        self.message_queue.put(("progress", (100, "Complete!")))
        self.message_queue.put(
            ("log", f"📊 Summary: {success_count}/{total} images processed successfully")
        )

        # List failed files if any
        if failed_files:
            self.message_queue.put(("log", ""))
            self.message_queue.put(("log", f"❌ Failed images ({len(failed_files)}):"))
            for filename in failed_files:
                self.message_queue.put(("log", f"   • {filename}"))

        return success_count, failed_files

    def _process_embed(self):
        """Process files for EXIF embedding with progress updates."""
        from pathlib import Path

        from .core.exif_utils import embed_exif_dates

        total = len(self.files)
        success_count = 0
        failed_files = []

        for i, img_path in enumerate(self.files, 1):
            # Update progress
            progress = int(10 + (80 * i / total))
            self.message_queue.put(
                ("progress", (progress, f"Processing {i}/{total}: {img_path.name}"))
            )

            # Log current file
            self.message_queue.put(("log", f"  [{i}/{total}] Processing: {img_path.name}"))

            # Embed EXIF dates
            success = embed_exif_dates(img_path, Path(self.output_dir))

            if success:
                success_count += 1
                if self.verbose:
                    self.message_queue.put(("log", "    ✅ Dates embedded successfully"))
            else:
                self.message_queue.put(("log", "    ⚠️  No EXIF dates found or processing failed"))
                failed_files.append(img_path.name)

        # Final progress
        self.message_queue.put(("progress", (100, "Complete!")))
        self.message_queue.put(
            ("log", f"📊 Summary: {success_count}/{total} images processed successfully")
        )

        # List failed files if any
        if failed_files:
            self.message_queue.put(("log", ""))
            self.message_queue.put(("log", f"⚠️  Images without EXIF dates ({len(failed_files)}):"))
            for filename in failed_files:
                self.message_queue.put(("log", f"   • {filename}"))

        return success_count, failed_files


def main():
    """Entry point for desktop GUI application."""
    # Create and run the application
    app = GPhotoMetaSyncGUI()
    app.run()


if __name__ == "__main__":
    main()
