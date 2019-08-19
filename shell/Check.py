from shell import casDocumentCreate
from shell import cloudosDocumentCreate
from docx import Document
from tcpping import tcpping
import time, os

def hostStatusCheck(hostInfo):
    error = list()
    for i in hostInfo:
        temp = str()
        #ssh端口检查
        if not tcpping(i['ip'], i['sshPort'], 2):
            if not temp:
                temp = '<br/>主机'+i['ip']+'&nbspssh端口连通异常'
            else:
                temp += ',ssh端口连通异常'
        if not tcpping(i['ip'], i['httpPort'], 2):
            if not temp:
                temp = '<br/>主机'+i['ip']+'&nbsphttp端口连通异常'
            else:
                temp += ',http端口连通异常'
        error += temp
        del temp
    return error


def Check(hostInfo):
    status = hostStatusCheck(hostInfo)
    document = Document()
    result = {"filename" : '', "content" : ''}
    for i in hostInfo:
        if i['role'] == 'cvm':
            print("cas巡检")
            cas = casDocumentCreate.casCheck(i['ip'], i['sshUser'], i['sshPassword'], i['httpUser'], i['httpPassword'])
            print("cas巡检完成")
            casDocumentCreate.cvmCheck(document, cas)
            casDocumentCreate.clusterCheck(document, cas)
            casDocumentCreate.cvkCheck(document, cas)
            casDocumentCreate.vmCheck(document, cas)
            casDocumentCreate.cvmHaChech(document, cas)
        elif i['role'] == 'cloudos':
            print("cloduos巡检")
            cloud = cloudosDocumentCreate.cloudosCheck(i['ip'], i['sshUser'], i['sshPassword'], i['httpUser'], i['httpPassword'])
            print("cloduos巡检")
            cloudosDocumentCreate.osBasicCheck(document, cloud)
            cloudosDocumentCreate.osPlatCheck(document, cloud)
        result['content'] += i['role'] + '\t'
    filename = "巡检文档" + time.strftime("%Y%m%d%H%M", time.localtime())+".docx"
    path = os.getcwd() + "//check_result//" + filename
    document.save(path)
    result['filename'] = filename
    return result

