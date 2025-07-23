import os
import subprocess
import json
import threading
import time
from flask import Flask, request, jsonify
from flask_cors import CORS
import re

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
        print(f"开始运行布局布线程序，文件: {filename}, 模块: {modulename}...")
        
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
        log_filename = f"{filename}_log.txt"
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"=== 执行时间: {time.ctime()}\n")
            f.write(f"=== 返回码: {result.returncode}\n")
            f.write("=== 标准输出:\n")
            f.write(result.stdout)
            f.write("\n=== 错误输出:\n")
            f.write(result.stderr)
            
        print(f"布局布线完成!日志文件: {log_filename}")
    except subprocess.TimeoutExpired:
        print("布局布线程序运行超时")
    except Exception as e:
        print(f"运行布局布线程序时出错: {str(e)}")

# 新增的Verilog处理函数
def process_verilog(verilog_code,filename, modulename):
    try:
        # 保存Verilog文件
        verilog_filename = f"{filename}.v"
        with open(verilog_filename, 'w') as f:
            f.write(verilog_code)
        print(f"Verilog文件已保存为{verilog_filename}")
        
        # 运行mos2json转换
        print("运行mos2json.exe...")
        mos2json_path = os.path.join(os.getcwd(), 'mos2json.exe')
        
        if not os.path.exists(mos2json_path):
            raise FileNotFoundError(f"mos2json.exe文件不存在: {mos2json_path}")
        
        mos2json_result = subprocess.run(
            [mos2json_path, '-f', verilog_filename, '-d', '-m'],
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
        json_filename = f"{filename}.v.json"
        run_layout_routing(json_filename, modulename)
        
        # 读取布局和布线结果文件
        try:
            with open('Layout_after.json', 'r') as f:
                layout_data = json.load(f)
            with open('Route_after.json', 'r') as f:
                route_data = json.load(f)
            print ('布局布线结果读取成功')
        except Exception as e:
            return False, f"读取布局布线结果失败: {str(e)}"
        
        return True, {
            "message": "Verilog处理成功，布局布线完成!",
            "layout": layout_data,
            "route": route_data
        }
    except Exception as e:
        return False, f"app处理Verilog时出错: {str(e)}"

# 新增预览布局布线路由
@app.route('/preview', methods=['GET'])
def preview_layout():
    try:
        print("开始预览布局布线...")
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
            
        return jsonify({
            'status': 'success',
            'message': '布局布线预览完成',
            'output': see_result.stdout,
            'error': see_result.stderr
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

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
        
        # 运行布局布线
        run_layout_routing('design.json', 'top_module')
        
        # 读取布局和布线结果文件
        try:
            with open('Layout_after.json', 'r') as f:
                layout_data = json.load(f)
            with open('Route_after.json', 'r') as f:
                route_data = json.load(f)
            print ('布局布线结果读取成功')
        except Exception as e:
            return False, f"读取布局布线结果失败: {str(e)}"
        
        return jsonify({
            'status': 'success',
            'message': '布局布线完成!',
            'layout': layout_data,
            'route': route_data
        })
    except Exception as e:
        return False, f"app处理Verilog时出错: {str(e)}"

# 新增的Verilog上传路由
@app.route('/upload_verilog', methods=['POST'])
def upload_verilog():
    # 检查请求数据
    if not request.json or 'verilog' not in request.json:
        return jsonify({
            'status': 'error',
            'message': '无效的请求数据'
        }), 400
    
    # 获取Verilog代码和新的参数
    verilog_code = request.json['verilog']
    filename = request.json.get('filename')  
    modulename = request.json.get('modulename')
    print('处理：' + filename + ' <-' + modulename)
    # 处理Verilog代码
    success, message = process_verilog(verilog_code, filename, modulename)
    if success:
        print('处理成功')
        return jsonify({
            'status': 'success',
            'message': 'Verilog处理成功，布局布线完成',
            'layout': message['layout'],
            'route': message['route']
        })
    else:
        print('处理失败')
        return jsonify({
            'status': 'error',
            'message': message
        }), 500

# 新增路由：获取仿真数据
@app.route('/get_simulation_data', methods=['POST'])
def get_simulation_data():
    if not request.json or 'filename' not in request.json:
        return jsonify({
            'status': 'error',
            'message': '无效的请求数据'
        }), 400
    try:
        # 读取并解析仿真文件
        filename = request.json.get('filename')
        modulename = request.json.get('modulename') 
        allfilename = filename + '.v.md'
        with open(allfilename, 'r') as f:
            content = f.read()
        print(filename + ' <- ' + modulename)
        print(content)
        # 查找模块部分
        module_match = re.search(fr'## module {modulename}\s+(.*?)(?=^## |\Z)', content, re.DOTALL | re.MULTILINE)
        if not module_match:
            print(f"未找到{modulename}模块")
            return jsonify({'status': 'error', 'message': 'module not found'}), 404
            
        module_content = module_match.group(1).strip()
        
        # 查找表格
        table_match = re.search(r'^\|.*?\|.*?\|$', module_content, re.MULTILINE)
        if not table_match:
            print("未找到表格")
            return jsonify({'status': 'error', 'message': 'Table not found'}), 404
        
        # 解析表头
        header_line = module_content.splitlines()[0]
        
        inout_line = module_content.splitlines()[2]
        inouts = [h.strip() for h in inout_line.split('|')[1:-1]]
        
        # 计算输入端口数量（输入列标题后连续出现的 | 数量）
        inputs_count = header_line.count('|', header_line.index('Inputs'), header_line.index('Outputs'))
        input_ports = inouts[:inputs_count]
        output_ports = inouts[inputs_count:]
        
        # 解析表格数据
        table_lines = module_content.splitlines()[2:]
        table = []
        
        for line in table_lines:
            if not line.startswith('|'):
                continue
            values = [v.strip() for v in line.split('|')[1:-1]]
            if len(values) != len(inouts):
                continue
            
            row = {}
            for i, header in enumerate(inouts):
                row[header] = values[i]
            table.append(row)
        print(input_ports)
        print(output_ports)
        print(table)
        return jsonify({
            'status': 'success',
            'module_name': modulename,
            'input_ports': input_ports,
            'output_ports': output_ports,
            'table': table
        })
    except Exception as e:
        print(f"解析文件时出错: {str(e)}")
        return jsonify({
            'status': 'error',
            'message': str(e)
        }), 500

if __name__ == '__main__':   
    # 启动Flask应用
    app.run(host='0.0.0.0', port=5000, debug=True)