import json
import subprocess
import socket
import urllib.parse as urlparser
import time

OFF_METHOD_KEY_PREFIX = "off-method_"
OFF_METHOD_SHUTDOWN = "shutdown"
OFF_METHOD_STOP = "stop"
# LXC不可设置为此项，否则会报错。
OFF_METHOD_SUSPEND = "suspend"

###############################################################
# 仅设置下面参数，其他地方不知道的不要改。
# Please only set these parameters below.

DEFAULT_OFF_METHOD = OFF_METHOD_SHUTDOWN
DEFAULT_OFF_METHOD_TIMEOUT = 30
# 是否必须关闭成功，如果为False，关闭超时后就不会再继续关闭，如果为True，关闭超时之后会强行关机。
MUST_OFF_SUCCESS = True

###############################################################

def exec_pvesh(act: str, path: [str], args: dict = None) -> dict:
    for i in range(len(path)):
        path[i] = urlparser.quote(path[i])

    path_str = str.join("/", path)
    exec_args = ["/bin/pvesh", act, "/" + path_str]
    if args is not None:
        for k, v in args.items():
            exec_args.append("-" + str(k) + "=" + str(v))
    exec_args.append("--output-format=json")
    
    process = subprocess.Popen(exec_args, stderr=subprocess.PIPE, stdout=subprocess.PIPE)
    stdout, stderr = process.communicate()
    exit_code = process.wait()

    if exit_code != 0:
        raise Exception("pvesh exit code is not 0: " + str(exit_code) + 
                        " /// stderr: " + stderr.decode("utf-8") + 
                        " /// stdout: " + stdout.decode("utf-8") + 
                        " /// args: " + str(args))
    
    # 接下来的返回值都是0的，说明都是符合预期的。
    # 对于处理成功但是解析json失败的， 就直接打出值。
    try:
        return json.loads(stdout.decode("utf-8"))
    except Exception:
        print("* plain text returned:", stdout.decode("utf-8"))
        return dict()

# node name是主机名的第一个.之前的部分。
def get_node(name: str) -> dict:
    return exec_pvesh("get", ["nodes", name, "status"])

def get_current_node_name() -> str:
    return socket.gethostname().split('.')[0]

# 获取QEMU或者LXC设置了哪种默认关闭方式的tag。
# 返回值为字符串，需要自己比对是不是预设的值。
def get_off_method(qemu_or_lxc: dict) -> str:
    tags_str = qemu_or_lxc.get('tags')
    if tags_str is not None:
        tags = tags_str.split(';')
        for tag in tags:
            if str(tag).startswith(OFF_METHOD_KEY_PREFIX):
                return str(tag).removeprefix(OFF_METHOD_KEY_PREFIX)
    
    # 默认为shutdown。
    return OFF_METHOD_SHUTDOWN

# 获取QEMU或者LXC设置的启动顺序，如果没设置就返回默认值0。
def get_shutdown_order(qemu_or_lxc: dict) -> int:
    startups_str = qemu_or_lxc.get('startup')
    if startups_str is not None:
        startups = startups_str.split(',')
        for startup in startups:
            if str(startup).startswith("order="):
                order = str(startup).removeprefix("order=")
                return int(order)

    return 0

# 获取QEMU或者LXC设置的优雅关机超时时间，如果没设置就返回默认值0。
def get_shutdown_timeout(qemu_or_lxc: dict) -> int:
    startups_str = qemu_or_lxc.get('startup')
    if startups_str is not None:
        startups = startups_str.split(',')
        for startup in startups:
            if str(startup).startswith("down="):
                timeout = str(startup).removeprefix("down=")
                return int(timeout)

    return 0

# 获取QEMU或者LXC的ID。
def get_id(vm_or_lxc: dict) -> int:
    return int(vm_or_lxc['vmid'])

# 判断QEMU或者LXC是否正在运行。
def is_qemu_or_lxc_running(node_name: str, qemu_or_lxc_id: int, qemu_or_lxc_type: str) -> bool:
    resp = exec_pvesh("get", ["nodes", node_name, qemu_or_lxc_type, str(qemu_or_lxc_id), "status", "current"])
    return resp["status"] == "running"

# 给QEMU发送ACPI关机信号或者等待LXC进程退出。
def shutdown_qemu_or_lxc(node_name: str, qemu_or_lxc_id: int, qemu_or_lxc_type: str, timeout: int):
    start_time = int(time.time())
    
    args = {"timeout": timeout}
    if MUST_OFF_SUCCESS:
        args["forceStop"] = 1
    
    exec_pvesh("create", ["nodes", node_name, qemu_or_lxc_type, str(qemu_or_lxc_id), "status", "shutdown"], args)
    
    end_time = int(time.time())
    print("* shutdown", qemu_or_lxc_type, ":", str(id), ", timeout:", str(timeout), ", process time:", str(end_time - start_time))

# 拔电关机。
def stop_qemu_or_lxc(node_name: str, qemu_or_lxc_id: int, qemu_or_lxc_type: str):
    start_time = int(time.time())
    
    exec_pvesh("create", ["nodes", node_name, qemu_or_lxc_type, str(qemu_or_lxc_id), "status", "stop"])
    
    end_time = int(time.time())
    print("* stop", qemu_or_lxc_type, ":", str(id), ", process time:", str(end_time - start_time))

# 暂停QEMU状态，保存到磁盘中。
def suspend_qemu(node_name: str, qemu_id: int):
    start_time = int(time.time())
    
    exec_pvesh("create", ["nodes", node_name, "qemu", str(qemu_id), "status", "suspend"], {"todisk": 1})
    
    end_time = int(time.time())
    print("* suspend qemu:", str(qemu_id), ", process time:", str(end_time - start_time))

# 获取QEMU或者LXC的(ID、启动顺序、类型、关闭方式、超时时间)列表，基于启动顺序反向排序。
def get_off_list(node_name: str) -> []:
    ret = []

    # 获取QEMU的。
    qemus = exec_pvesh("get", ["nodes", node_name, "qemu"])
    for qemu in qemus:
        id = get_id(qemu)
        config = exec_pvesh("get", ["nodes", node_name, "qemu", str(id), "config"])

        off_method = get_off_method(config)
        if off_method != OFF_METHOD_SHUTDOWN and \
           off_method != OFF_METHOD_STOP and \
           off_method != OFF_METHOD_SUSPEND:
            print("* unknown off method of qemu", id, ":", off_method, ", use default:", DEFAULT_OFF_METHOD)
            off_method = DEFAULT_OFF_METHOD

        order = get_shutdown_order(config)
        timeout = get_shutdown_timeout(config)
        if timeout == 0:
            timeout = DEFAULT_OFF_METHOD_TIMEOUT

        ret.append((id, order, "qemu", off_method, timeout))

    # 获取LXC的。
    lxcs = exec_pvesh("get", ["nodes", node_name, "lxc"])
    for lxc in lxcs:
        id = get_id(lxc)
        config = exec_pvesh("get", ["nodes", node_name, "lxc", str(id), "config"])

        off_method = get_off_method(config)
        if off_method != OFF_METHOD_SHUTDOWN and \
           off_method != OFF_METHOD_STOP:
            print("* unknown off method of lxc", id, ":", off_method, ", use default:", DEFAULT_OFF_METHOD)
            off_method = DEFAULT_OFF_METHOD

        order = get_shutdown_order(config)
        timeout = get_shutdown_timeout(config)
        if timeout == 0:
            timeout = DEFAULT_OFF_METHOD_TIMEOUT

        ret.append((id, order, "lxc", off_method, timeout))

    # 反向排序。
    ret.sort(key=lambda x: x[1], reverse=True)
    return ret

def off(node_name: str, qemu_or_lxc_id: int, qemu_or_lxc_type: str, method: str, timeout: int):
    if not is_qemu_or_lxc_running(node_name, qemu_or_lxc_id, qemu_or_lxc_type):
        print("*", qemu_or_lxc_type, ":", str(qemu_or_lxc_id), "is not running, skipped")
        return
    
    if method == OFF_METHOD_SHUTDOWN:
        shutdown_qemu_or_lxc(node_name, qemu_or_lxc_id, qemu_or_lxc_type, timeout)
    elif method == OFF_METHOD_STOP:
        stop_qemu_or_lxc(node_name, qemu_or_lxc_id, qemu_or_lxc_type)
    elif method == OFF_METHOD_SUSPEND:
        suspend_qemu(node_name, qemu_or_lxc_id)

if __name__ == "__main__":
    if MUST_OFF_SUCCESS:
        print("* must off success")
    
    hostname = socket.gethostname()
    print("* current hostname:", hostname)
    node_name = hostname.split('.')[0]
    print("* current node name:", node_name)

    off_list = get_off_list(node_name)
    print("* ordered off list:", str(off_list))

    # 依次执行关闭操作。
    for order in off_list:
        try:
            id = order[0]
            type = order[2]
            method = order[3]
            timeout = order[4]
            off(node_name, id, type, method, timeout)
        except Exception as e:
            print("* off error:", str(e), ", skipped")
            continue

