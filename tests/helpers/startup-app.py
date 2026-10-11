"""A deliberately slow app for real pointer/launch-feedback regression checks."""
import time
with open("/tmp/aurora-startup-audit-count", "a") as count:
    count.write("started\n")
time.sleep(3)
import gi
gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

app = Gtk.Application(application_id="org.aurora.StartupAudit")
def activate(application):
    window = Gtk.ApplicationWindow(application=application, title="Startup Audit",
                                    default_width=500, default_height=400)
    window.set_child(Gtk.Label(label="The application is ready"))
    window.present()
app.connect("activate", activate)
app.run([])
