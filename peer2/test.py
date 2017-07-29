
def register(filename, clientID):
    idList = []
    if filename in index.keys():
        idList = index.get(filename)    
    idList.append(clientID)
    index[filename] = idList
    

def search(filename):
    if filename in index.keys():
        return index.get(filename)
    else:
        return 'File not found.'

register('Hello.py', 45) 
register('Zip.py', 45)  
register('Hello.py', 46) 
register('Hello.py', 47) 
command = 'REGISTER'
print(index)
print(search('Hello.py'))
print(command.lower() is 'REGISTER')