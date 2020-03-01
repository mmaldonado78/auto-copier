import sys
import os
import subprocess
import argparse
from pexpect import popen_spawn, EOF
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from time import sleep

class AutoCopier:

    def __init__(self):
        self.source = ""
        self.dest = ""
        self.basename = ""
        self._parse_commands()

    def _parse_commands(self):

        parser = argparse.ArgumentParser()
        parser.add_argument("-fe", "--force-execution", type=str, help="After a file change" +
                    "is detected, ", action="store")
        parser.add_argument("watchdir", help="Directory to watch for changes")
        parser.add_argument("targetdir", help="Directory where changed files are copied to")
        # parser.add_argument("host", help="Remote device to connect to")
        if len(sys.argv) != 3:
            print("Invalid input\n")
            quit()

        self.source = sys.argv[1]
        self.dest = sys.argv[2]

        if not os.path.exists(self.source):
            print("Directory not found\n")
            quit()

        if self.source == ".":
            self.source = os.getcwd()

        if self.source[-1] == "\\" or self.source[-1] == "/":
            self.source = self.source[:len(self.source) - 1]

        if not self.dest.endswith("/") and not self.dest.endswith(":"):
            self.dest += "/"

        self.basename = os.path.split(self.source)[1]

        print("Source path: %s, Dest path: %s, Directory basename: %s" %
              (self.source, self.dest, self.basename))

    def run(self):
        event_handler = Handler(self.basename, self.dest, patterns=["*.py"],
                                ignore_patterns=["*.py___jb_old___", "*.py___jb_temp___"])

        observer = Observer()
        observer.schedule(event_handler, self.source)
        observer.start()

        try:
            while True:
                sleep(1)
        except KeyboardInterrupt:
            observer.stop()

        observer.join()



class Handler(PatternMatchingEventHandler):
    """Event handler for observer."""

    def __init__(self, basename, dest, patterns=None, ignore_patterns=None):
        self.last_time = 0
        self.most_recent_time = 0
        self.last_path = ""
        self.most_recent_path = ""
        self.basename = basename
        self.dest = dest

        PatternMatchingEventHandler.__init__(self, patterns, ignore_patterns)

    def on_created(self, event):
        print("Detected file creation: Path: %s\n" % event.src_path)

    def on_modified(self, event):
        self.most_recent_time = os.stat(event.src_path).st_mtime
        self.most_recent_path = event.src_path

        print("Last modification: %d, Most recent modification: %d" %
              (self.last_time, self.most_recent_time))

        # Account for possible duplicate modification events but allow detection
        # of more than one file changing in watch cycle
        if self.last_path != self.most_recent_path or \
                (self.last_path == self.most_recent_path and
                 self.most_recent_time - self.last_time > .5):

            rel_path = self._get_rel_path(event.src_path)

            print("Detected file modification:\n\tPath: %s\n\tRelative Path: %s"
                  % (event.src_path, rel_path))

            self.copy_file(event.src_path, self.dest, rel_path)

        self.last_time = self.most_recent_time
        self.last_path = self.most_recent_path



    def on_deleted(self, event):
        print("Detected file deletion:\n\tPath: %s\n" % event.src_path)

    def on_moved(self, event):

        if len(event.src_path) > len(event.dest_path):
            diff = event.src_path.replace(event.dest_path, "")
        else:
            diff = event.dest_path.replace(event.src_path, "")

        # print("Diff between paths: %s\n" % diff)

        if diff != "___jb_tmp___" and diff != "___jb_old___":

            print("Detected moved/renamed file:\n\tOld path: %s\n\tNew path: %s\n" %
                    (event.src_path, event.dest_path))

    def _get_rel_path(self, event_source_path):
        rel_path = event_source_path.partition(self.basename)[2]
        rel_path = rel_path.replace("\\\\", "/")
        rel_path = rel_path.replace("\\", "/")

        if rel_path.startswith("/"): rel_path = rel_path[1:]

        return rel_path

    def copy_file(self, source_path, dest_path, rel_path):

        cmd = "scp %s %s%s" % (source_path, dest_path, rel_path)
        # child = popen_spawn.PopenSpawn(cmd, encoding='utf-8')
        # # child.delaybeforesend = 1
        # # res1 = child.expect('assword:', timeout=None)
        #
        #
        # # if res1 == 0: print("Matched password prompt")
        #
        # # child.sendline('maker')
        #
        # child.expect(EOF)
        # res = child.expect(["No such file or directory", "100%"], timeout=30)
        # if res == 0:
        #     print("File transfer failed\n")
        #     child.kill(0)
        #
        # elif res == 1:
        #     print("File transfer succeeded\n")
        #
        # print(child.before)
        # print(child.after)
        # child.logfile = sys.stdout

        pscp_path = "C:\Program Files\PuTTY\pscp.exe"
        dest_full_path = dest_path + rel_path
        subprocess.call([pscp_path, "-sftp", "-pw", "maker", source_path,
                         dest_full_path])



if __name__ == "__main__":

    auto_copier = AutoCopier()
    auto_copier.run()



