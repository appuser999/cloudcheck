from requests.auth import HTTPDigestAuth
import xmltodict, requests
from shell.Cas3Data import Cas3Data
from shell import applog
logfile = applog.Applog()

class Cas5Data(Cas3Data):

    def cvkVswitch(self, cvk):
        if cvk['status'] == '1':
            response = requests.get(self.url + 'host/id/' + cvk['id'] + '/vswitch', cookies=self.cookies)
            contxt1 = response.text
            response.close()
            dict2 = xmltodict.parse(contxt1)
            # print(dict2)
            li = []
            if 'list' in dict2.keys():  # 5.0为host
                dict1 = dict2['list']
            else:
                return li
            temp = []
            if isinstance(dict1, dict):
                if isinstance(dict1['vSwitch'], dict):
                    temp.append(dict1['vSwitch'])
                else:
                    temp = dict1['vSwitch'].copy()
                for h in temp:
                    temp1 = {}
                    temp1['name'] = h['name']
                    temp1['status'] = h['status']
                    temp1['pnic'] = h['pnic']
                    li.append(temp1.copy())
                    del temp1
            del temp
            del dict1
            del dict2
            cvk['vswitch'] = li
        return