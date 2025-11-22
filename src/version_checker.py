import requests
import customtkinter as ctk
from tkinter import messagebox
import webbrowser
import os

class VersionChecker:
    def __init__(self):
        self.current_version = "2.0.0"
        self.github_repo = "dainn-dev/trans"
        self.latest_release_url = f"https://api.github.com/repos/{self.github_repo}/releases/latest"
        
    def check_for_updates(self, parent_window=None):
        try:
            response = requests.get(self.latest_release_url)
            if response.status_code == 200:
                latest_release = response.json()
                latest_version = latest_release['tag_name'].replace('v', '')
                
                if self._compare_versions(latest_version, self.current_version) > 0:
                    self._show_update_notification(parent_window, latest_version, latest_release['html_url'])
                    return True
            return False
        except Exception as e:
            print(f"Error checking for updates: {e}")
            return False
    
    def _compare_versions(self, version1, version2):
        v1_parts = [int(x) for x in version1.split('.')]
        v2_parts = [int(x) for x in version2.split('.')]
        
        for i in range(max(len(v1_parts), len(v2_parts))):
            v1 = v1_parts[i] if i < len(v1_parts) else 0
            v2 = v2_parts[i] if i < len(v2_parts) else 0
            
            if v1 > v2:
                return 1
            elif v1 < v2:
                return -1
        return 0
    
    def _show_update_notification(self, parent_window, latest_version, download_url):
        if parent_window:
            # Create a custom dialog
            dialog = ctk.CTkToplevel(parent_window)
            dialog.title("Update Available")
            dialog.geometry("400x250")
            dialog.transient(parent_window)
            dialog.grab_set()
            
            # Center the dialog
            dialog.update_idletasks()
            width = dialog.winfo_width()
            height = dialog.winfo_height()
            x = (dialog.winfo_screenwidth() // 2) - (width // 2)
            y = (dialog.winfo_screenheight() // 2) - (height // 2)
            dialog.geometry(f'{width}x{height}+{x}+{y}')
            
            # Add content
            ctk.CTkLabel(
                dialog,
                text="A new version is available!",
                font=("Helvetica", 16, "bold")
            ).pack(pady=10)
            
            ctk.CTkLabel(
                dialog,
                text=f"Current version: {self.current_version}\nLatest version: {latest_version}",
                font=("Helvetica", 12)
            ).pack(pady=5)
            
            # Add release notes if available
            try:
                response = requests.get(f"https://api.github.com/repos/{self.github_repo}/releases/latest")
                if response.status_code == 200:
                    release_data = response.json()
                    if release_data.get('body'):
                        notes_frame = ctk.CTkFrame(dialog)
                        notes_frame.pack(pady=10, padx=20, fill="both", expand=True)
                        
                        notes_label = ctk.CTkLabel(
                            notes_frame,
                            text="What's New:",
                            font=("Helvetica", 12, "bold")
                        )
                        notes_label.pack(pady=(5, 0))
                        
                        notes_text = ctk.CTkLabel(
                            notes_frame,
                            text=release_data['body'],
                            font=("Helvetica", 11),
                            wraplength=350
                        )
                        notes_text.pack(pady=5)
            except Exception as e:
                print(f"Error fetching release notes: {e}")
            
            # Add buttons
            button_frame = ctk.CTkFrame(dialog)
            button_frame.pack(pady=20)
            
            def download_update():
                webbrowser.open(download_url)
                dialog.destroy()
            
            def skip_update():
                dialog.destroy()
            
            ctk.CTkButton(
                button_frame,
                text="Download Update",
                command=download_update
            ).pack(side="left", padx=10)
            
            ctk.CTkButton(
                button_frame,
                text="Skip",
                command=skip_update
            ).pack(side="left", padx=10)
        else:
            # Fallback to simple messagebox if no parent window
            if messagebox.askyesno(
                "Update Available",
                f"A new version ({latest_version}) is available!\n\n"
                f"Current version: {self.current_version}\n\n"
                "Would you like to download the update?"
            ):
                webbrowser.open(download_url) 