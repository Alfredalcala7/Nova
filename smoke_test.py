import customtkinter as ctk

app = ctk.CTk()
app.title("Nova smoke test")
app.geometry("320x160")

label = ctk.CTkLabel(app, text="Clicks: 0")
label.pack(pady=20)

count = 0  # throwaway test, so a global is fine here

def on_click():
    global count
    count += 1
    label.configure(text=f"Clicks: {count}")

ctk.CTkButton(app, text="Click me", command=on_click).pack()
app.mainloop()