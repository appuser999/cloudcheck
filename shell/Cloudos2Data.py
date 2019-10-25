from requests.auth import HTTPBasicAuth
import math
import json
import re
import requests
import paramiko
from shell import images, applog

logfile = applog.Applog()

class Cloudos2Data:
    def __init__(self, ip, sshuser, sshpassword, httpuser, httppassword):
        self.ip = ip
        self.sshuser = sshuser
        self.sshpassword = sshpassword
        self.httpuser = httpuser
        self.httppassword = httppassword
        self.osInfo = {}
        return


    # 获取Token
    def getToken(self, ip, username, password):
        data = {"auth": {"identity": {"methods": ["password"], "password": {"user": {
            "name": "", "password": "", "domain": {"id": "default"}}}}, "scope": {"project": {
            "name": "admin", "domain": {"id": "default"}}}}}

        #3.0 body字段
        # data = {
        #     "identity": {
        #         "method": "password",
        #         "user": {
        #             "name": "admin",
        #             "password": "admin"
        #         }
        #     }
        # }
        # cloudos 3.0 url：
        # url = "http://" + ip + ":8000/sys/identity/v2/tokens"

        data['auth']['identity']['password']['user']['name'] = username
        data['auth']['identity']['password']['user']['password'] = password
        headers = {'content-type': 'application/json', 'Accept': 'application/json', 'X-Auth-Token': ''}
        url = "http://" + ip + ":9000/v3/auth/tokens"
        respond = requests.post(url, json.dumps(data), headers=headers)
        token = respond.headers['X-Subject-Token']
        respond.close()
        return token

    #获取cloudos服务器硬件信息和软件版本
    @applog.logRun(logfile)
    def cloudosBasicCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        #服务器型号
        stdin, stdout, stderr = ssh.exec_command("dmidecode | grep -i product | awk '{print $0}' | cut -d : -f 2")
        if not stderr.read():
            self.osInfo['productVersion'] = stdout.read().decode()

        #服务器规格
        stdin, stdout, stderr = ssh.exec_command("lscpu | cut -d : -f 2 | awk 'NR==4 || NR==7{print $1}';free -g | awk 'NR==2{print $2}'")
        if not stderr.read():
            text = stdout.read().decode()
            str1 = text.splitlines()
            self.osInfo['deviceDmide'] = "cpu:" + str1[0] + "*" + str1[1] + "cores" + "\nMem:" + str1[2] + 'G'

        #cloudos版本
        stdin, stdout, stderr = ssh.exec_command("docker images | grep openstack-com | head -1 | awk '{print $2}'")
        if not stderr.read():
            self.osInfo['version'] = stdout.read().decode()
        ssh.close()
        return

    # 发现Node节点设备、并查询状态
    @applog.logRun(logfile)
    def NodeCollect(self):
        self.osInfo["nodeInfo"] = []
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command(
            "/opt/bin/kubectl -s 127.0.0.1:8888 get nodes | awk 'NR>1{print $1,$2}'")
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = {}
                dict1['hostName'] = line.split()[0]
                dict1['status'] = line.split()[1]
                self.osInfo['nodeInfo'].append(dict1)
                line = stdout.readline()
        else:
            print(stderr.read())
        ssh.close()
        return

    #发现主节点
    @applog.logRun(logfile)
    def findMaster(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        self.osInfo['masterIP'] = ""
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tsystemctl status deploy-manager | grep Active | awk '{print $3}' | sed -e 's/(//g' | sed -e 's/)//g'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                text = stdout.read().decode().strip()
                if text == 'running':
                    self.osInfo['masterIP'] = i["hostName"]
        return

    #查看磁盘分区空间分配是否合规
    #规格：centos-root>201G,centos-swap>33.8G,centos-metadata>5.3G,centos-data>296G
    @applog.logRun(logfile)
    def diskCapacity(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                i['diskCapacity'] = []
                cmd = "ssh\t" + i["hostName"] + "\tfdisk -l | grep /dev/mapper/centos | awk '{print $2,$5/1000/1000/1000}' | sed -e 's/://g' | sed -e 's/\/dev\/mapper\///g'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                text = stdout.read().decode()
                lines = text.splitlines()
                for j in lines:
                    dict1 = {}
                    dict1['name'] = j.split()[0]
                    dict1['capacity'] = (float)(j.split()[1])
                    i['diskCapacity'].append(dict1.copy())
                    del dict1
        return

    # 查询磁盘利用率，磁盘利用率大于0.8属于不正常
    @applog.logRun(logfile)
    def diskRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            i['diskRate'] = []
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tdf -h | grep -v tmp | cut -d % -f 1 | awk 'NR>1{print $1,$5/100}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    line = stdout.readline()
                    temp = {}
                    while line:
                        temp['name'] = line.split()[0]
                        temp['rate'] = (float)(line.split()[1])
                        line = stdout.readline()
                        i['diskRate'].append(temp.copy())
                    del temp
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 查询内存利用率,利用率大于0.8属于不正常
    @applog.logRun(logfile)
    def memRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tfree | grep Mem | awk '{print $3/$2}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    i['memRate'] = float(stdout.read().decode())
                else:
                    print(stderr.read())
        ssh.close()
        return

    #查询cpu利用率,利用率大于0.8属于不正常
    @applog.logRun(logfile)
    def cpuRateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\t vmstat | awk 'NR>2{print (100-$15)/100}'"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    i['cpuRate'] = float(stdout.read().decode())
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 容器状态检查，正常容器状态为Running
    @applog.logRun(logfile)
    def containerStateCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command("/opt/bin/kubectl -s 127.0.0.1:8888 get pod | awk 'NR>1{print $1,$3}'")
        self.osInfo['ctainrState'] = list()
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = {}
                dict1['name'] = line.split()[0]
                dict1['status'] = line.split()[1]
                self.osInfo['ctainrState'].append(dict1.copy())
                line = stdout.readline()
                del dict1
        else:
            print(stderr.read())
        ssh.close()
        return

    # 查看共享磁盘是否存在是否正常断开,当状态为True时，表示正常断开无异常；
    # 当状态为False时，表示断开异常
    @applog.logRun(logfile)
    def shareStorErrorCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command("cat /var/log/messages | grep EXT4 | grep error")
        for i in self.osInfo['nodeInfo']:
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i["hostName"] + "\tcat /var/log/messages | grep EXT4 | grep error"
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    if not stdout.read():
                        i["shareStorError"] = True
                    else:
                        i["shareStorError"] = False
                else:
                    print(stderr.read())
        ssh.close()
        return

    # 检查容器分布是否均匀
    #当状态为False表示为分布不均，当状态为True是表示分布均匀
    @applog.logRun(logfile)
    def containerLBCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 get node | awk 'NR>1{print$1}' | while read line;do echo $line $(/opt/bin/kubectl -s 127.0.0.1:8888 get pod -o wide | grep $line | wc -l);done"
        stdin, stdout, stderr = ssh.exec_command(cmd)
        li = []
        if not stderr.read():
            line = stdout.readline()
            while line:
                dict1 = {}
                dict1['NodeName'] = line.split()[0]
                dict1['ctainrNum'] = int(line.split()[1])
                li.append(dict1.copy())
                line = stdout.readline()
                del dict1
            sum = 0
            length = len(li)
            for i in li:
                sum += i['ctainrNum']  # 容器总数
            sum2 = 0
            for j in li:
                sum2 += math.pow(sum / length - j['ctainrNum'], 2)  # 求容器分布的方差
            if sum2 / length > 9:  # 方差大于9时则分布不均
                self.osInfo['ctainrLB'] = False
            else:
                self.osInfo['ctainrLB'] = True
        else:
            print(stderr.read())
        ssh.close()
        return

    #检查容器镜像是否完整
    @applog.logRun(logfile)
    def dockerImageCheck(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            i['images'] = set()
            set1 = set()
            if i["status"] == 'Ready':
                cmd = "ssh\t" + i['hostName'] + "\tdocker images | awk 'NR>1{print $1}' | grep -v gcr | grep -v\t" + self.osInfo['masterIP']
                stdin, stdout, stderr = ssh.exec_command(cmd)
                if not stderr.read():
                    text = stdout.read().decode()
                    for j in text.splitlines():
                        set1.add(j)
                    # 当为v2版本使用v2的镜像集合进行对比
                    if i['hostName'] == self.osInfo['masterIP']:
                        if set1 == images.imagesv2Set:
                            i["images"] = set()
                        else:
                            i["images"] = images.imagesv2Set.difference(set1)
                    else:
                        if set1 == images.imagesv2Set - {'registry'}:
                            i["images"] = set()
                        else:
                            i["images"] = (images.imagesv2Set - {'registry'}).difference(set1)
                else:
                    print("docker Image check ssh is invalid")
        ssh.close()
        return

    #检查ntp时间是否一致
    @applog.logRun(logfile)
    def nodeNtpTimeCollect(self):
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        for i in self.osInfo['nodeInfo']:
            cmd = "ssh\t" + i['hostName'] + "\tntpdate -q\t"+ self.osInfo["masterIP"] +"\t| awk 'NR==1{print $6}' | cut -d - -f 2 | cut -d , -f 1"
            sdtin, stdout, stderr = ssh.exec_command(cmd)
            i['ntpOffset'] = (float)(stdout.read())
        ssh.close()
        return

    def getImage2Pod(self):
        cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 get pod | awk 'NR>1{print $1}'| while read line;do " \
              "/opt/bin/kubectl -s 127.0.0.1:8888 describe pod $line | grep Image: |awk -v var1=$line '" \
              "{print var1,$2}' | cut -d : -f 1;done"
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        stdin, stdout, stderr = ssh.exec_command(cmd)
        text = stdout.read().decode().strip()
        dic1 = {}
        for i in text.splitlines():
            if not i.split()[1] in dic1.keys():
                dic1[i.split()[1]] = []
            dic1[i.split()[1]].append(i.split()[0])
        ssh.close()
        return dic1

    # 检查openstack-compute和openstack内的关键服务是否正常
    @applog.logRun(logfile)
    def containerServiceCollect(self):
        self.osInfo['serviceStatus'] = {}
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(self.ip, 22, self.sshuser, self.sshpassword)
        pods = self.getImage2Pod()
        version = self.osInfo['version'][0] + self.osInfo['version'][1]
        for i in images.services[version].keys():
            podlist = pods[i]
            for pod in podlist:
                self.osInfo['serviceStatus'][pod] = []
                for j in images.services[version][i]:
                    dict1 = {}
                    dict1['name'] = j
                    # cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 exec -it " + pod + " systemctl status " + j + " | grep Active | awk '{print $2}'"
                    cmd = "/opt/bin/kubectl -s 127.0.0.1:8888 exec -i " + pod + " systemctl status " + j + " | grep Active | awk '{print $3}'"
                    stdin, stdout, stderr = ssh.exec_command(cmd)
                    status = status = re.findall(r'\((.*?)\)', stdout.read().decode().strip())[0]
                    if status == "running":
                        dict1['status'] = True
                    else:
                        dict1['status'] = False
                    self.osInfo['serviceStatus'][pod].append(dict1.copy())
        return

    # 检查云主机镜像是否正常
    @applog.logRun(logfile)
    def imageCollect(self):
        self.osInfo["imagesStatus"] = []
        respond = requests.get("http://" + self.ip + ":9000/v3/images", auth = HTTPBasicAuth(self.httpuser, self.httppassword))
        if respond.text:
            tmp = json.loads(respond.text)
            if 'image' in tmp:
                for i in tmp['images']:
                    dict1 = {}
                    dict1['name'] = i['name']
                    dict1['status'] = i['status']
                    self.osInfo["imagesStatus"].append(dict1.copy())
                    del dict1
        respond.close()
        return

    # "status": "ACTIVE"
    # "name": "new-server-test"
    @applog.logRun(logfile)
    def vmCollect(self):
        self.osInfo['vmStatus'] = list()
        response = requests.get("http://" + self.ip + ":9000/v3/projects", auth = HTTPBasicAuth(self.httpuser, self.httppassword))
        for i in json.loads(response.text)['projects']:
            if 'cloud' in i.keys() and i['cloud'] is True:     # if后的逻辑运算从左到右
                url = "http://" + self.ip + ":9000/v2/" + i['id'] + "/servers/detail"
                response1 = requests.get(url, auth = HTTPBasicAuth(self.httpuser, self.httppassword))
                for j in json.loads(response1.text)['servers']:
                    dict1 = {}
                    dict1['name'] = j['name']
                    dict1['status'] = j['status']
                    self.osInfo['vmStatus'].append(dict1.copy())
                    del dict1
                response1.close()
        response.close()
        return

    # 'status': 'available'
    @applog.logRun(logfile)
    def vdiskCollect(self):
        self.osInfo['vDiskStatus'] = []
        response = requests.get("http://" + self.ip + ":9000/v3/projects", auth = HTTPBasicAuth(self.httpuser, self.httppassword))
        for i in json.loads(response.text)['projects']:
            if 'cloud' in i.keys() and i['cloud'] is True:  # if后的逻辑运算从左到右
                url = "http://" + self.ip + ":9000/v2/" + i['id'] + "/volumes/detail"
                response1 = requests.get(url, auth = HTTPBasicAuth(self.httpuser, self.httppassword))
                for j in json.loads(response1.text)['volumes']:
                    dict1 = {}
                    dict1['name'] = j['name']
                    dict1['status'] = j['status']
                    self.osInfo['vDiskStatus'].append(dict1.copy())
                    del dict1
                response1.close()
        response.close()
        return