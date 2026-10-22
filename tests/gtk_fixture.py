import gi

gi.require_version("Gtk", "3.0")
from gi.repository import Gtk  # noqa: E402 -- select GI version before importing

window = Gtk.Window(title="NekoWorker Integration")
window.set_default_size(500, 240)
box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
entry = Gtk.Entry()
entry.get_accessible().set_name("Message")
button = Gtk.Button(label="Submit")
label = Gtk.Label(label="Waiting")
button.connect("clicked", lambda _: label.set_text("Received: " + entry.get_text()))
for widget in (entry, button, label):
    box.pack_start(widget, True, True, 0)
window.add(box)
window.connect("destroy", Gtk.main_quit)
window.show_all()
Gtk.main()
