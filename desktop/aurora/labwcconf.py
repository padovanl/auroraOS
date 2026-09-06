"""Read and edit the user's labwc configuration (~/.config/labwc/rc.xml).

Settings pages use this to change compositor options (input devices,
keyboard, workspaces, shortcuts, decorations). Every save triggers
`labwc --reconfigure`, so changes apply immediately.
"""

import os
import subprocess
import xml.etree.ElementTree as ET

from aurora import data_path


def path():
    return os.path.join(os.path.expanduser("~/.config/labwc"), "rc.xml")


class Config:
    def __init__(self):
        p = path()
        if not os.path.exists(p):
            os.makedirs(os.path.dirname(p), exist_ok=True)
            src = data_path("labwc", "rc.xml")
            with open(src) as f, open(p, "w") as g:
                g.write(f.read())
        parser = ET.XMLParser(target=ET.TreeBuilder(insert_comments=True))
        self.tree = ET.parse(p, parser)
        self.root = self.tree.getroot()

    def node(self, *tags, create=True):
        """Return the element at root/tags[0]/tags[1]/..., creating it if asked."""
        cur = self.root
        for tag in tags:
            nxt = cur.find(tag)
            if nxt is None:
                if not create:
                    return None
                nxt = ET.SubElement(cur, tag)
            cur = nxt
        return cur

    def get(self, *tags, default=""):
        n = self.node(*tags, create=False)
        return n.text.strip() if n is not None and n.text else default

    def set(self, *tags, value):
        self.node(*tags).text = str(value)

    def device(self, category):
        """<libinput><device category="..."> element."""
        libinput = self.node("libinput")
        for dev in libinput.findall("device"):
            if dev.get("category") == category:
                return dev
        return ET.SubElement(libinput, "device", category=category)

    def device_get(self, category, tag, default=""):
        n = self.device(category).find(tag)
        return n.text.strip() if n is not None and n.text else default

    def device_set(self, category, tag, value):
        dev = self.device(category)
        n = dev.find(tag)
        if n is None:
            n = ET.SubElement(dev, tag)
        n.text = str(value)

    # --- keybinds ---

    def keybinds(self):
        """[(key, action_name, command_or_None, element)]"""
        out = []
        for kb in self.node("keyboard").findall("keybind"):
            action = kb.find("action")
            if action is None:
                continue
            out.append((kb.get("key"), action.get("name"), action.get("command"), kb))
        return out

    def add_command_keybind(self, key, command):
        kb = ET.SubElement(self.node("keyboard"), "keybind", key=key)
        kb.set("aurora-custom", "yes")
        ET.SubElement(kb, "action", name="Execute", command=command)

    def remove(self, element):
        for parent in self.root.iter():
            if element in list(parent):
                parent.remove(element)
                return

    def save(self):
        self.tree.write(path(), encoding="unicode", xml_declaration=True)
        if os.environ.get("AURORA_COMPOSITOR") == "wayfire":
            from aurora.wayfireconf import generate
            generate()
        else:
            subprocess.run(["labwc", "--reconfigure"], stderr=subprocess.DEVNULL, check=False)
