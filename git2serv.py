#Script used to update files from github server to your remote server via ssh

import git
from pathlib import Path
import shutil
import paramiko
import os
import sys
import time
import configparser
from collections import OrderedDict
from secret_info import ssh_pass_key, ssh_pass


class PushCode:
    # init for declaring variables for class
    def __init__(self, username, project, pkg_name, server, ssh_key, ssh_user):
        """

        :param username: Username for the local directory from host
        :param project: Name of the folder you want to copy to and from the remote server
        :param pkg_name: name of the package from a git server
        :param server: FQDN of the server, paramiko should read your host file if you have it there as a short name
        :param ssh_key: name of the key in your .ssh folder
        :param ssh_user: username on the remote server to work with.
        """
        self.user = username
        self.pjt = project
        self.pkg = f"{pkg_name}"
        if sys.platform == "linux":
            self.home = "/home/"
        elif sys.platform == "darwin":
            self.home = "/Users"
        elif sys.platform == "win32":
            self.home = "C:'\'Users"

        self.kfile = "{}/{}/.ssh/{}".format(self.home, username, ssh_key)
        self.path = "{}/{}/{}".format(self.home,self.user, self.pjt)
        self.ws = f"/var/www/{project}"
        self.host = server
        self.ssh_user = ssh_user

    # Using path and shutil to delete old git repo folder
    def clean_folder(self):
        cf = Path(self.path)
        if cf.is_dir():
            shutil.rmtree(self.path)
        else:
            cf.mkdir()
        print("Dir structure set up")

    # Checking out folder
    def checkout(self):
        git.Repo.clone_from(self.pkg, self.path)
        print("Repo has {} been checked out".format(self.pkg))

    # Sending the repo to the server
    def send_package(self):
        sordir = []
        # os walk for loop to get the absolute path from the source
        for root, directories, filenames in os.walk(self.path):
            for directory in directories:
                sordir.append(os.path.join(root, directory))
            for filename in filenames:
                sordir.append(os.path.join(root, filename))
        desdir = []
        # os walk for loop to only get the sub directories path for destination
        for root, dirs, files in os.walk(self.path):
            for d in dirs:
                desdir.append(os.path.join(root.replace(self.path, ""), d))
            for f in files:
                desdir.append(os.path.join(root.replace(self.path, ""), f))
        sd = OrderedDict((key, value) for key, value in zip(sordir, desdir))
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        ssh.connect(hostname=self.host, port=22, username=self.ssh_user, password=ssh_pass_key, key_filename=self.kfile)
        cpy = ssh.open_sftp()
        # Confirm if folder exists remotely, if it does delete and remake or create.
        try:
            cpy.lstat(self.pjt)
        except FileNotFoundError:
            ssh.exec_command("mkdir {}".format(self.pjt))
        else:
            ssh.exec_command("rm -rf {}".format(self.pjt))
            ssh.exec_command("mkdir {}".format(self.pjt))
        # scp-ing files, if Path confirms the item is a dir, it will create, otherwise it will put file into server.
        print("Sending repo to remote server")
        for k, v in sd.items():
            if Path(k).is_dir():
                ssh.exec_command("mkdir {}/{}".format(self.pjt, v))
            elif Path(k).is_file():
                cpy.put(k, "{}/{}".format(self.pjt, v))
        cpy.close()
        ssh.close()
        print("Repo has been sent")

    # Function used to backup the venv folder, delete previous manhattan, create and sync files across & start server.
    def setup_env(self):
        print("Now moving new repo to the web server and restarting apache")
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy)
        ssh.connect(hostname=self.host, port=22, username=self.ssh_user, password=ssh_pass_key, key_filename=self.kfile)
        stdin, stdout, stderr = ssh.exec_command("sudo rm -rf {}".format(self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("sudo mkdir {}".format(self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("sudo rsync -avv {}/ {}/".format(self.pjt, self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("sudo cp my.cnf {}/Manhattan/".format(self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("sudo chown www-data:www-data {}/ -R".format(self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(3)
        stdin, stdout, stderr = ssh.exec_command("sudo cp -r venv {}/".format(self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(5)
        stdin, stdout, stderr = ssh.exec_command("sudo {}/venv/bin/python3 {}/manage.py collectstatic --noinput".format(self.ws,
                                                                                                         self.ws), get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        time.sleep(2)
        stdin, stdout, stderr = ssh.exec_command("sudo systemctl restart apache2", get_pty=True)
        stdin.write(ssh_pass + "\n")
        stdin.flush()
        ssh.close()
        print("Folders have been migrated, remember to change the settings file to comment "
              "out STATIC_FILE_DIRS and restart apache2")
        print("Please also double check that VENV folder has been copied fully")


def main():
    # Adding arguments for the script
    conf = configparser.ConfigParser()
    conf.read("main.cfg")
    user = conf.get("Setup", "username")
    pjt = conf.get("Setup", "project")
    pkg = conf.get("Setup", "pkg_name")
    srv = conf.get("Setup", "server")
    key = conf.get("Setup", "ssh_key")
    ssh_user = conf.get("Setup", "ssh_user")
    up_server = PushCode(user, pjt, pkg, srv, key, ssh_user)
    up_server.clean_folder()
    up_server.checkout()
    up_server.send_package()
    up_server.setup_env()


if __name__ == "__main__":
main()
