"""Real Tk geometry regressions, enabled explicitly on the Windows build runner."""

import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from contextlib import nullcontext


@unittest.skipUnless(sys.platform == 'win32' and os.environ.get('SRA_GUI_TESTS') == '1',
                     'Real Windows GUI checks run in the dedicated CI step.')
class LayoutTests(unittest.TestCase):
    @staticmethod
    def destroy_root(root):
        import tkinter as tk
        try:
            for timer in root.tk.call('after', 'info'):
                root.after_cancel(timer)
            root.destroy()
        except tk.TclError:
            pass

    def make_app(self, scaling):
        import tkinter as tk
        from src.desktop import ArchiveApp
        root = tk.Tk()
        root.tk.call('tk', 'scaling', scaling)
        app = ArchiveApp(root, restore=False)
        self.addCleanup(self.destroy_root, root)
        return root, app

    def assert_visible(self, widget, root):
        self.assertTrue(widget.winfo_ismapped(), widget)
        self.assertGreater(widget.winfo_width(), 10)
        self.assertGreater(widget.winfo_height(), 10)
        left, top = widget.winfo_rootx(), widget.winfo_rooty()
        right, bottom = left + widget.winfo_width(), top + widget.winfo_height()
        ancestor = widget.master
        while ancestor is not None:
            self.assertGreaterEqual(left, ancestor.winfo_rootx() - 1)
            self.assertGreaterEqual(top, ancestor.winfo_rooty() - 1)
            self.assertLessEqual(right, ancestor.winfo_rootx() + ancestor.winfo_width() + 1)
            self.assertLessEqual(bottom, ancestor.winfo_rooty() + ancestor.winfo_height() + 1)
            if ancestor is root:
                break
            ancestor = ancestor.master

    def test_primary_actions_fit_small_windows_at_100_150_200_percent(self):
        for scale in (96 / 72, 144 / 72, 192 / 72):
            root, app = self.make_app(scale)
            for size in ('720x480', '800x500', '1100x780'):
                root.geometry(size)
                for page, button in ((app.setup, app.analyze_button),
                                     (app.topic_page, app.classify_button),
                                     (app.paper_page, app.accept_button)):
                    with self.subTest(scaling=scale, size=size, page=page):
                        app.tabs.select(page)
                        root.update()
                        self.assert_visible(button, root)
                        self.assert_visible(app.stop_button, root)
            self.destroy_root(root)

    def test_setup_scrolls_to_form_bottom_without_moving_action_bar(self):
        root, app = self.make_app(192 / 72)
        root.geometry('720x480')
        root.update()
        viewport = app.setup_scroll.canvas
        before = app.analyze_button.winfo_rooty()
        self.assertGreater(float(viewport.cget('scrollregion').split()[3]), viewport.winfo_height())
        viewport.yview_moveto(1)
        root.update()
        self.assertAlmostEqual(viewport.yview()[1], 1, places=2)
        self.assertEqual(before, app.analyze_button.winfo_rooty())
        self.assert_visible(app.analyze_button, root)

    def test_wheel_scrolls_only_its_own_page_and_preserves_text_scrolling(self):
        root, app = self.make_app(192 / 72)
        root.geometry('720x480')
        root.update()
        viewport = app.setup_scroll.canvas
        start = viewport.yview()
        event = SimpleNamespace(widget=app.account_box.master, delta=-120, state=0, num=0)
        self.assertEqual(app.setup_scroll.wheel(event), 'break')
        root.update()
        self.assertGreater(viewport.yview()[0], start[0])
        unchanged = viewport.yview()
        event.widget = app.details
        self.assertIsNone(app.setup_scroll.wheel(event))
        self.assertEqual(viewport.yview(), unchanged)

    def test_delete_connection_requires_confirmation_and_clears_account_and_models(self):
        root, app = self.make_app(96 / 72)
        state = {'host_id': 'synthetic-host', 'active': 'synthetic-client', 'profiles': [
            {'client_id': 'synthetic-client', 'email': 'test@example.invalid', 'refresh_token': 'synthetic-token'}]}
        app.restore_accounts(state)
        app.models = [{'slug': 'mock', 'display_name': 'Mock'}]
        app.model_box.configure(values=['Mock'])
        app.model.set('Mock')
        with patch('src.desktop.messagebox.askyesno', return_value=False), patch.object(app, 'start') as start:
            app.delete_connection()
            start.assert_not_called()
        self.assertEqual(len(app.accounts), 1)
        def run_now(job, done):
            done(job())
        with patch('src.desktop.messagebox.askyesno', return_value=True), \
                patch('src.desktop.messagebox.showinfo'), \
                patch('src.desktop.load', return_value=state), \
                patch('src.desktop.session_lock', return_value=nullcontext()), \
                patch('src.chatgpt_auth.revoke_session', return_value=True), \
                patch('src.chatgpt_auth.save'), patch.object(app, 'start', side_effect=run_now):
            app.delete_connection()
        self.assertEqual(app.accounts, [])
        self.assertIsNone(app.account_id)
        self.assertEqual(app.account.get(), 'Neues Konto / Workspace')
        self.assertEqual(app.models, [])
        self.assertEqual(app.model.get(), '')


if __name__ == '__main__':
    unittest.main()
