import sys
import os
import socket
import subprocess
import argparse
from pexpect import popen_spawn, EOF
from datetime import datetime
from watchdog.observers import Observer
from watchdog.events import PatternMatchingEventHandler
from ssh2.session import Session
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
        self.sm = SessionManager()

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

        cmd = "scp %s %s%s\n" % (source_path, dest_path, rel_path)
        print(cmd)

        # ------------------------------------------------
        # ------------------------- With PSCP ------------
        # ------------------------------------------------

        # pscp_path = "C:\Program Files\PuTTY\pscp.exe"
        # dest_full_path = dest_path + rel_path
        # subprocess.call([pscp_path, "-sftp", "-pw", "maker", source_path,
        #                  dest_full_path])

        # ------------------------------------------------
        # --------------------- With SSH2 ----------------
        # ------------------------------------------------

        self.sm.scp(source_path, dest_path + rel_path)



class SessionManager:
    """Opens an SSH session"""

    def __init__(self):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect(("ev3dev", 22))

        self.session = Session()
        self.session.handshake(sock)
        self.session.userauth_password("robot", "maker")
        self.session.keepalive_config(True, 60)

    def run_remote_cmd(self, cmd):
        chan = self.session.open_session()
        chan.execute(cmd)

        # Read output
        output = ""
        size, data = chan.read()
        while size > 0:
            output += data.decode('utf-8')
            print(data.decode('utf-8'))
            size, data = chan.read()

        sig, err, lang_tag = chan.get_exit_signal()
        print(err.decode('utf-8'))

        chan.close()

        return sig, output

    def scp(self, src_path, dest_path):

        fileinfo = os.stat(src_path)

        chan = self.session.scp_send64(dest_path, fileinfo.st_mode & 0o777, fileinfo.st_size,
                                fileinfo.st_mtime, fileinfo.st_atime)

        # Output Stats
        now = datetime.now()
        with open(src_path, 'rb') as local_fh:
            for data in local_fh:
                chan.write(data)
        taken = datetime.now() - now
        rate = (fileinfo.st_size / 1024000.0) / taken.total_seconds()
        print("Finished writing %s to remote in %s |  %.4f. MB/s" %
              (dest_path, taken, rate))

        chan.close()

    def disconnect(self):
        self.session.disconnect()


if __name__ == "__main__":

    auto_copier = AutoCopier()
    auto_copier.run()



