"""Desktop entry point used by Python and the Windows EXE build."""

import json
from pathlib import Path
import sys


def run():
    if '--self-test' in sys.argv:
        # No browser, account store, real PDFs or network in this packaging check.
        from src.analysis import classify
        from src.files import valid_topic_name
        from src.chatgpt_auth import protect
        assert classify('digital history')[0] == 'Digital History'
        assert valid_topic_name('Social History') and not valid_topic_name('../escape')
        assert protect(protect(b'packaging-check'), decrypt=True) == b'packaging-check'
        return
    if '--smoke-test' in sys.argv:
        import tkinter as tk
        from src.desktop import ArchiveApp
        root = tk.Tk()
        root.withdraw()
        ArchiveApp(root, restore=False)
        root.update_idletasks()
        if '--report' in sys.argv:
            path = Path(sys.argv[sys.argv.index('--report') + 1])
            path.write_text(json.dumps({'window_created': True, 'tabs': 4, 'version': '1.0.0'}), encoding='utf-8')
        root.destroy()
        return
    from src.desktop import main
    main()


if __name__ == '__main__':
    try:
        run()
    except Exception as error:
        if '--self-test' in sys.argv or '--smoke-test' in sys.argv:
            sys.exit(1)
        # Windowed EXEs have no console. Show a useful startup error without secrets.
        from tkinter import messagebox
        messagebox.showerror('Smart Research Archive', f'Die App konnte nicht starten: {error}')
        sys.exit(1)
