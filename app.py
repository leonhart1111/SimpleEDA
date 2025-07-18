# app.py
import os
import subprocess
import json
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

# 保存设计数据的函数
def save_design(data):
    with open('design.json', 'w') as f:
        json.dump(data, f, indent=2)

# 运行布局布线程序的函数
def run_layout_routing(filename, modulename):
    # 等待文件写入完成
    time.sleep(0.5)
    
    # 运行布局布线程序
    try:
        print("开始运行布局布线程序...")
        
        # 获取TestRoute.exe的绝对路径
        test_route_path = os.path.join(os.getcwd(), 'TestRoute.exe')
        
        # 检查文件是否存在
        if not os.path.exists(test_route_path):
            error_msg = f"TestRoute.exe文件不存在: {test_route_path}"
            print(error_msg)
            raise FileNotFoundError(error_msg)
        
        # 检查执行权限
        if not os.access(test_route_path, os.X_OK):
            error_msg = f"TestRoute.exe没有执行权限: {test_route_path}"
            print(error_msg)
            raise PermissionError(error_msg)
        
        # 执行程序并捕获详细输出
        result = subprocess.run(
            [test_route_path, '-f' ,filename, '-m', modulename],
            capture_output=True,
            text=True,
            timeout=120
        )
        
        # 将输出写入日志文件
        with open('test_route_log.txt', 'w', encoding='utf-8') as f:
            f.write(f"=== 执行时间: {time.ctime()}\n")
            f.write(f"=== 返回码: {result.returncode}\n")
            f.write("=== 标准输出:\n")
            f.write(result.stdout)
            f.write("\n=== 错误输出:\n")
            f.write(result.stderr)
            
        print("运行see.py...")
        see_result = subprocess.run(
            ['python', 'see.py'],
            capture_output=True,
            text=True
        )
        print("see.py输出:")
        print(see_result.stdout)
        if see_result.stderr:
            print("see.py错误:")
            print(see_result.stderr)
            
        print("布局布线完成!")
    except subprocess.TimeoutExpired:
        print("布局布线程序运行超时")
    except Exception as e:
        print(f"运行布局布线程序时出错: {str(e)}")

# 新增的Verilog处理函数
def process_verilog(verilog_code):
    try:
        # 保存Verilog文件
        with open('top_module.v', 'w') as f:
            f.write(verilog_code)
        print("Verilog文件已保存为 top_module.v")
        
        # 运行mos2json转换
        print("运行mos2json.exe...")
        mos2json_path = os.path.join(os.getcwd(), 'mos2json.exe')
        
        if not os.path.exists(mos2json_path):
            raise FileNotFoundError(f"mos2json.exe文件不存在: {mos2json_path}")
        
        mos2json_result = subprocess.run(
            [mos2json_path, '-f', 'top_module.v', '-d'],
            capture_output=True,
            text=True,
            timeout=60
        )
        
        # 检查转换结果
        if mos2json_result.returncode != 0:
            error_msg = f"mos2json转换失败: {mos2json_result.stderr}"
            print(error_msg)
            return False, error_msg
        
        print("mos2json转换成功!")
        
        # 运行布局布线
        run_layout_routing('top_module.v.json', 'top_module')
        
        return True, "Verilog处理成功，布局布线完成!"
    except Exception as e:
        return False, f"处理Verilog时出错: {str(e)}"

@app.route('/upload', methods=['POST'])
def upload_design():
    # 检查请求数据
    if not request.json or 'circuit' not in request.json:
        return jsonify({
            'status': 'error',
            'message': 'Invalid request data'
        }), 400
    
    # 获取电路设计数据
    circuit_data = request.json['circuit']
    
    try:
        # 保存设计数据
        save_design(circuit_data)
        print("设计数据已保存到 design.json")
        
        # 立即返回接收成功响应
        response = jsonify({
            'status': 'success',
            'message': '布局数据接收成功，开始后台处理'
        })
        
        # 在后台线程中运行布局布线程序
        threading.Thread(
            target=run_layout_routing,
            args=('design.json', 'top_module'),
            daemon=True
        ).start()
        
        return response
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'保存设计数据时出错: {str(e)}'
        }), 500

# 新增的Verilog上传路由
@app.route('/upload_verilog', methods=['POST'])
def upload_verilog():
    # 检查请求数据
    if not request.json or 'verilog' not in request.json:
        return jsonify({
            'status': 'error',
            'message': '无效的请求数据'
        }), 400
    
    # 获取Verilog代码
    verilog_code = request.json['verilog']
    
    try:
        # 在后台线程中处理Verilog
        def process_in_thread():
            success, message = process_verilog(verilog_code)
            print(message)
        
        threading.Thread(target=process_in_thread, daemon=True).start()
        
        return jsonify({
            'status': 'success',
            'message': 'Verilog文件已接收，正在处理中...'
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'处理Verilog时出错: {str(e)}'
        }), 500

@app.route('/status', methods=['GET'])
def check_status():
    # 检查布局布线程序是否仍在运行
    # 实际应用中应实现更精确的状态跟踪
    return jsonify({
        'status': 'processing',
        'message': '布局布线程序正在运行，请稍候...'
    })

if __name__ == '__main__':   
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)