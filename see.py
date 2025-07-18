import json
import plotly.graph_objects as go
import plotly.io as pio
import colorsys
import math
import webbrowser

# 设置默认模板
pio.templates.default = "plotly_white"

def generate_distinct_colors(n, saturation=0.8, lightness=0.6):
    """生成一组视觉上可区分的颜色"""
    colors = []
    for i in range(n):
        hue = i / n
        r, g, b = colorsys.hls_to_rgb(hue, lightness, saturation)
        colors.append(f'rgb({int(r*255)},{int(g*255)},{int(b*255)})')
    return colors

def visualize_circuit_interactive(layout_file, route_file, output_html="preview.html"):
    """
    交互式可视化电路布局和布线信息
    
    参数:
        layout_file: 布局JSON文件路径
        route_file: 布线JSON文件路径
        output_html: 输出HTML文件名
    """
    # 读取布局数据
    with open(layout_file, 'r') as f:
        layout_data = json.load(f)
    
    # 读取布线数据
    with open(route_file, 'r') as f:
        route_data = json.load(f)
    
    top_module = next(iter(layout_data.keys()))
    top_module_data = layout_data[top_module]
    
    # 获取布线模块数据
    route_module = next(iter(route_data.keys()))
    route_module_data = route_data[route_module]
    
    # 确定电路整体边界
    min_x, min_y, max_x, max_y = calculate_circuit_boundaries(top_module_data)
    circuit_width = max_x - min_x
    circuit_height = max_y - min_y

    # 确保最小尺寸，避免零或过小尺寸
    min_dimension = 100  # 最小显示尺寸
    circuit_width = max(circuit_width, min_dimension)
    circuit_height = max(circuit_height, min_dimension)
    
    # 创建图形
    fig = go.Figure()
    
    # 收集所有网络用于生成颜色
    all_nets = collect_all_nets(route_module_data)
    net_colors = generate_distinct_colors(len(all_nets))
    net_color_map = {net: net_colors[i] for i, net in enumerate(all_nets)}
    
    # 递归绘制布局（不再使用min_size_ratio）
    draw_layout_recursive(fig, top_module_data, 0, top_module, 
                         circuit_width=circuit_width, 
                         circuit_height=circuit_height)
    
    # 递归绘制布线
    draw_routing_recursive(fig, route_module_data, net_color_map)
    
    # 设置图形布局
    fig.update_layout(
        title=f'交互式电路可视化: {top_module}',
        xaxis_title='X 坐标',
        yaxis_title='Y 坐标',
        showlegend=True,
        legend_title='网络',
        hovermode='closest',
        autosize=True,
        height=800,
        margin=dict(l=50, r=50, b=50, t=80),
        xaxis=dict(
            scaleanchor="y",
            scaleratio=1,
            constrain='domain',
            range=[min_x - circuit_width*0.05, max_x + circuit_width*0.05]
        ),
        yaxis=dict(
            constrain='domain',
            range=[min_y - circuit_height*0.05, max_y + circuit_height*0.05]
        ),
        clickmode='event+select'
    )
    
    # 添加自定义缩放功能
    fig.update_layout(
        updatemenus=[
            dict(
                type="buttons",
                direction="left",
                buttons=list([
                    dict(
                        args=["yaxis.scaleanchor", "x"],
                        args2=["xaxis.scaleratio", 1],
                        label="锁定比例",
                        method="relayout"
                    ),
                    dict(
                        args=["yaxis.scaleanchor", None],
                        args2=["xaxis.scaleratio", None],
                        label="解锁比例",
                        method="relayout"
                    ),
                    dict(
                        args=["yaxis.autorange", True],
                        args2=["xaxis.autorange", True],
                        label="重置视图",
                        method="relayout"
                    ),
                    dict(
                        label="隐藏所有连线",
                        method="restyle",
                        args=[{}]
                    )
                ]),
                pad={"r": 10, "t": 10},
                showactive=True,
                x=0.05,
                xanchor="left",
                y=1.1,
                yanchor="top"
            )
        ]
    )
    
    # 添加动态细节显示的JavaScript - 修改为基于当前视图区域
    js_code = """
    <script>
    function toggleAllNets(gd) {
        let allHidden = true;
        gd.data.forEach(trace => {
            if (trace.legendgroup && trace.legendgroup.startsWith('net_')) {
                if (trace.visible !== false) {
                    allHidden = false;
                }
            }
        });
        
        const newVisibility = allHidden ? true : false;
        const updates = {};
        gd.data.forEach((trace, i) => {
            if (trace.legendgroup && trace.legendgroup.startsWith('net_')) {
                updates[`visible[${i}]`] = newVisibility;
            }
        });
        
        Plotly.restyle(gd, updates);
        
        const buttonIndex = gd.layout.updatemenus[0].buttons.findIndex(
            btn => btn.label.includes('隐藏') || btn.label.includes('显示')
        );
        if (buttonIndex !== -1) {
            const newLabel = newVisibility ? '隐藏所有连线' : '显示所有连线';
            Plotly.relayout(gd, `updatemenus[0].buttons[${buttonIndex}].label`, newLabel);
        }
    }

    function updateDetailVisibility() {
        const gd = document.getElementById('graph');
        if (!gd) return;

        const xRange = gd.layout.xaxis.range;
        const yRange = gd.layout.yaxis.range;

        if (!xRange || !yRange) return;

        const viewWidth = xRange[1] - xRange[0];
        const viewHeight = yRange[1] - yRange[0];

        // 动态阈值：基于当前视图区域的大小
        // 使用视图区域宽高中较大的一个作为参考
        const viewMaxDim = Math.max(viewWidth, viewHeight);
        const moduleThreshold = viewMaxDim / 20;   // 模块显示阈值
        const labelThreshold = viewMaxDim / 15;    // 标签显示阈值

        // 遍历所有模块
        gd.data.forEach(trace => {
            if (trace.meta && trace.meta.type) {
                const width = trace.meta.width || 0;
                const height = trace.meta.height || 0;
                const maxDim = Math.max(width, height);
                let visible = true;
                let showLabel = true;

                // 根据当前视图区域决定是否显示
                if (maxDim < moduleThreshold) {
                    visible = false;  // 太小则不显示
                } else if (maxDim < labelThreshold) {
                    // 显示轮廓但不显示标签
                    if (trace.meta.type.endsWith('-label')) {
                        visible = false;  // 隐藏标签
                    }
                }

                // 对于标签类型，额外检查其父元素是否可见
                if (trace.meta.type.endsWith('-label')) {
                    // 查找对应的轮廓元素
                    const parentIndex = trace.index - 1; // 假设标签紧跟在轮廓之后
                    if (parentIndex >= 0 && gd.data[parentIndex] && gd.data[parentIndex].meta) {
                        const parentVisible = gd.data[parentIndex].visible;
                        if (!parentVisible) {
                            visible = false;
                        }
                    }
                }

                // 设置可见性
                Plotly.restyle(gd, { visible: visible }, [trace.index]);
            }
        });
    }

    // 绑定事件
    document.addEventListener('DOMContentLoaded', function () {
        const gd = document.getElementById('graph');
        if (gd) {
            gd.on('plotly_relayout', updateDetailVisibility);
            gd.on('plotly_button_click', function(data) {
                if (data.button.label.includes('隐藏') || data.button.label.includes('显示')) {
                    toggleAllNets(gd);
                }
            });
            setTimeout(updateDetailVisibility, 1000); // 初始执行一次
        }
    });
    </script>
    """
    
    # 保存为HTML文件（添加自定义JS）
    fig.write_html(output_html, include_plotlyjs='cdn', auto_open=False)
    
    # 在生成的HTML中添加JavaScript
    with open(output_html, 'a') as f:
        f.write(js_code)
    
    print(f"交互式可视化已保存至: {output_html}")
    webbrowser.open(output_html)

def calculate_circuit_boundaries(module_data):
    """递归计算电路边界"""
    min_x, min_y = float('inf'), float('inf')
    max_x, max_y = float('-inf'), float('-inf')
    
    if 'layout' in module_data:
        layout = module_data['layout']
        x = layout['x']
        y = layout['y']
        width = layout['width']
        height = layout['height']
        
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x + width)
        max_y = max(max_y, y + height)
    
    # 处理端口（忽略wire类型）
    if 'ports' in module_data:
        for port_name, port_data in module_data['ports'].items():
            # 跳过wire类型端口，因其坐标可能为极大值
            if port_data.get('type') == 'wire':
                continue
            port_layout = port_data['layout']
            px = port_layout['x']
            py = port_layout['y']
            pwidth = port_layout['width']
            pheight = port_layout['height']
            
            min_x = min(min_x, px)
            min_y = min(min_y, py)
            max_x = max(max_x, px + pwidth)
            max_y = max(max_y, py + pheight)
    
    # 处理晶体管
    if 'mosfets' in module_data:
        for mosfet_name, mosfet_data in module_data['mosfets'].items():
            mosfet_layout = mosfet_data['layout']
            mx = mosfet_layout['x']
            my = mosfet_layout['y']
            mwidth = mosfet_layout['width']
            mheight = mosfet_layout['height']
            
            min_x = min(min_x, mx)
            min_y = min(min_y, my)
            max_x = max(max_x, mx + mwidth)
            max_y = max(max_y, my + mheight)
    
    # 递归处理子模块
    if 'subModules' in module_data:
        for sub_name, sub_data in module_data['subModules'].items():
            sub_layout = sub_data['layout']
            sub_min_x, sub_min_y, sub_max_x, sub_max_y = calculate_circuit_boundaries(
                sub_data)
            
            min_x = min(min_x, sub_min_x)
            min_y = min(min_y, sub_min_y)
            max_x = max(max_x, sub_max_x)
            max_y = max(max_y, sub_max_y)
    
    # 处理未找到任何元件的情况
    if min_x == float('inf'):
        return 0, 0, 4444, 4444  # 默认边界
    return min_x, min_y, max_x, max_y

def draw_layout_recursive(fig, module_data, depth, module_instance_name, 
                         circuit_width=1000, circuit_height=1000):
    """
    递归绘制布局模块，支持动态细节展示
    
    修改: 不再使用min_size_ratio，改为在客户端动态控制
    """
    module_colors = [
        '#FF6B6B', '#4ECDC4', '#556270', 
        '#C06C84', '#FFAA85', '#6A0572'
    ]
    
    component_colors = {
        'input': '#2ecc71', 'output': '#EDAEDA', 'power': '#f1c40f',
        'wire': '#3498db', 'nmos': '#9b59b6', 'pmos': '#e67e22', 
        'default': '#95a5a6'
    }
    
    if 'layout' in module_data:
        layout = module_data['layout']
        x = layout['x']
        y = layout['y']
        width = layout['width']
        height = layout['height']
        
        # 模块颜色
        module_color = module_colors[depth % len(module_colors)]
        border_width = max(1, 4 - depth)  # 深度越大，边框越细
        
        # 添加模块矩形
        fig.add_trace(go.Scatter(
            x=[x, x+width, x+width, x, x],
            y=[y, y, y+height, y+height, y],
            mode='lines',
            line=dict(color=module_color, width=border_width),
            fill='toself',
            fillcolor=f'rgba({int(module_color[1:3], 16)}, {int(module_color[3:5], 16)}, {int(module_color[5:7], 16)}, 0.125)',  # 半透明填充（转换为RGBA格式）
            hoverinfo='text',
            hovertext=f"模块: {module_instance_name}<br>类型: {module_data.get('type', 'Unknown')}<br>尺寸: {width:.2f}x{height:.2f}<br>位置: ({x:.2f}, {y:.2f})",
            name=module_instance_name,
            legendgroup=f"module_{depth}",
            showlegend=depth == 0,  # 只在顶层显示图例
            meta={'type': 'module', 'width': width, 'height': height}
        ))
        
        # 添加模块标签
        module_type = module_data.get('type', 'Unknown')
        display_name = f"{module_instance_name} ({module_type})"
        
        # 计算字体大小（基于模块尺寸）
        font_size = max(8, min(14, int(math.sqrt(width * height) * 0.1)))
        
        fig.add_annotation(
            x=x + width * 0.98,
            y=y + height * 0.98,
            xref="x",
            yref="y",
            text=display_name,
            showarrow=False,
            font=dict(size=font_size, color=module_color),
            bgcolor="rgba(255,255,255,0.7)",
            bordercolor=module_color,
            borderwidth=1,
            borderpad=2,
            xanchor="right",
            yanchor="top"
        )
    
    # 绘制端口
    if 'ports' in module_data:
        for port_name, port_data in module_data['ports'].items():
            port_layout = port_data['layout']
            px = port_layout['x']
            py = port_layout['y']
            pwidth = max(0.5, port_layout['width'] * 0.8)
            pheight = max(0.5, port_layout['height'] * 0.8)
            ptype = port_data['type']
            
            color = component_colors.get(ptype, component_colors['default'])
            
            if ptype != 'wire':  # 忽略连线端口
                # 绘制端口矩形
                fig.add_trace(go.Scatter(
                    x=[px, px+pwidth, px+pwidth, px, px],
                    y=[py, py, py+pheight, py+pheight, py],
                    mode='lines',
                    line=dict(color=color, width=1),
                    fill='toself',
                    fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.5)',  # 半透明填充（转换为RGBA格式）
                    hoverinfo='text',
                    hovertext=f"端口: {port_name}<br>类型: {ptype}<br>位置: ({px:.2f}, {py:.2f})",
                    name=f"端口: {port_name}",
                    legendgroup="ports",
                    meta={'type': 'port', 'width': pwidth, 'height': pheight}
                ))
                
                # 添加端口标签
                fig.add_trace(go.Scatter(
                    x=[px + pwidth/2],
                    y=[py + pheight/2],
                    mode='text',
                    text=port_name,
                    textposition="middle center",
                    textfont=dict(size=8),
                    hoverinfo='skip',
                    showlegend=False,
                    legendgroup="ports",
                    meta={'type': 'port-label', 'width': pwidth, 'height': pheight}
                ))
    
    # 绘制晶体管
    if 'mosfets' in module_data:
        for mosfet_name, mosfet_data in module_data['mosfets'].items():
            mosfet_layout = mosfet_data['layout']
            mx = mosfet_layout['x']
            my = mosfet_layout['y']
            mwidth = max(1, mosfet_layout['width'] * 0.8)
            mheight = max(1, mosfet_layout['height'] * 0.8)
            mtype = mosfet_data['type']
            
            color = component_colors.get(mtype, component_colors['default'])
            
            # 绘制晶体管矩形
            fig.add_trace(go.Scatter(
                x=[mx, mx+mwidth, mx+mwidth, mx, mx],
                y=[my, my, my+mheight, my+mheight, my],
                mode='lines',
                line=dict(color=color, width=1.5),
                fill='toself',
                fillcolor=f'rgba({int(color[1:3], 16)}, {int(color[3:5], 16)}, {int(color[5:7], 16)}, 0.375)',  # 半透明填充（转换为RGBA格式）
                hoverinfo='text',
                hovertext=f"晶体管: {mosfet_name}<br>类型: {mtype}<br>位置: ({mx:.2f}, {my:.2f})",
                name=f"晶体管: {mosfet_name}",
                legendgroup="transistors",
                meta={'type': 'transistor', 'width': mwidth, 'height': mheight}
            ))
            
            # 添加晶体管标签
            fig.add_trace(go.Scatter(
                x=[mx + mwidth/2],
                y=[my + mheight/2],
                mode='text',
                text=mosfet_name,
                textposition="middle center",
                textfont=dict(size=8),
                hoverinfo='skip',
                showlegend=False,
                legendgroup="transistors",
                meta={'type': 'transistor-label', 'width': mwidth, 'height': mheight}
            ))
    
    # 递归处理子模块
    if 'subModules' in module_data:
        for sub_name, sub_data in module_data['subModules'].items():
            sub_layout = sub_data['layout']
            draw_layout_recursive(
                fig, 
                sub_data,
                depth + 1, 
                sub_name,
                circuit_width,
                circuit_height
            )

def collect_all_nets(module_data):
    """递归收集所有网络信息"""
    all_nets = set()
    
    # 添加当前模块的网络
    if 'nets' in module_data:
        for net in module_data['nets']:
            all_nets.add(net.get('name', 'unknown'))
    
    # 递归处理子模块
    if 'subModules' in module_data:
        for sub_name, sub_data in module_data['subModules'].items():
            all_nets.update(collect_all_nets(sub_data))
    
    return list(all_nets)

def draw_routing_recursive(fig, route_data, net_color_map, offset_x=0, offset_y=0):
    """递归绘制布线信息"""
    # 绘制当前模块的布线
    draw_routing_with_offset(fig, route_data, net_color_map, offset_x, offset_y)
    
    # 递归处理子模块
    if 'subModules' in route_data:
        for sub_name, sub_data in route_data['subModules'].items():
            # 假设子模块有布局信息，需要偏移
            if 'layout' in sub_data:
                sub_offset_x = offset_x + sub_data['layout']['x']
                sub_offset_y = offset_y + sub_data['layout']['y']
            else:
                sub_offset_x = offset_x
                sub_offset_y = offset_y
                
            draw_routing_recursive(fig, sub_data, net_color_map, sub_offset_x, sub_offset_y)

def draw_routing_with_offset(fig, route_data, net_color_map, offset_x=0, offset_y=0):
    """绘制当前模块的布线信息（带偏移量）"""
    for net in route_data.get('nets', []):
        net_name = net.get('name', 'unknown')
        color = net_color_map.get(net_name, 'rgb(150,150,150)')
        
        # 收集所有点用于悬停信息
        line_x = []
        line_y = []
        via_x = []
        via_y = []
        pin_x = []
        pin_y = []
        hover_texts = []
        
        # 绘制线段
        for segment in net.get('segments', []):
            start = segment.get('start', {})
            end = segment.get('end', {})
            layer = segment.get('layer', 0)
            
            x1 = start.get('x', 0) + offset_x
            y1 = start.get('y', 0) + offset_y
            x2 = end.get('x', 0) + offset_x
            y2 = end.get('y', 0) + offset_y
            
            # 添加到线路径
            line_x.append(x1)
            line_y.append(y1)
            hover_texts.append(f"网络: {net_name}<br>起点: ({x1:.2f}, {y1:.2f})<br>层: {layer}")
            
            line_x.append(x2)
            line_y.append(y2)
            hover_texts.append(f"网络: {net_name}<br>终点: ({x2:.2f}, {y2:.2f})<br>层: {layer}")
            
            line_x.append(None)
            line_y.append(None)
            hover_texts.append(None)
        
        # 绘制引脚
        for pin in net.get('pins', []):
            x = pin.get('x', 0) + offset_x
            y = pin.get('y', 0) + offset_y
            pin_x.append(x)
            pin_y.append(y)
            hover_texts.append(f"引脚: {net_name}<br>位置: ({x:.2f}, {y:.2f})")
        
        # 绘制过孔
        for via in net.get('vias', []):
            x = via.get('x', 0) + offset_x
            y = via.get('y', 0) + offset_y
            via_x.append(x)
            via_y.append(y)
            hover_texts.append(f"过孔: {net_name}<br>位置: ({x:.2f}, {y:.2f})")
        
        # 添加线段
        if line_x:
            fig.add_trace(go.Scatter(
                x=line_x,
                y=line_y,
                mode='lines',
                line=dict(color=color, width=1.5),
                hoverinfo='text',
                hovertext=hover_texts[:len(line_x)],
                name=net_name,
                legendgroup=f"net_{net_name}",
                showlegend=True
            ))
        
        # 添加过孔
        if via_x:
            fig.add_trace(go.Scatter(
                x=via_x,
                y=via_y,
                mode='markers',
                marker=dict(
                    symbol='square',
                    size=6,
                    color=color,
                    line=dict(width=1, color='black')
                ),
                hoverinfo='text',
                hovertext=hover_texts[len(line_x):len(line_x)+len(via_x)],
                name=f"{net_name} 过孔",
                legendgroup=f"net_{net_name}",
                showlegend=False
            ))
        
        # 添加引脚
        if pin_x:
            fig.add_trace(go.Scatter(
                x=pin_x,
                y=pin_y,
                mode='markers',
                marker=dict(
                    symbol='circle',
                    size=5,
                    color=color,
                    line=dict(width=1, color='black')
                ),
                hoverinfo='text',
                hovertext=hover_texts[len(line_x)+len(via_x):],
                name=f"{net_name} 引脚",
                legendgroup=f"net_{net_name}",
                showlegend=False
            ))

if __name__ == "__main__":
    layout_file = "Layout_after.json"
    route_file = "Route_after.json"
    output_html = "preview.html"
    
    try:
        visualize_circuit_interactive(layout_file, route_file, output_html)
    except FileNotFoundError as e:
        print(f"错误: 文件未找到 - {str(e)}")
        print("请确保JSON文件在当前目录中存在。")
    except json.JSONDecodeError as e:
        print(f"错误: JSON格式无效 - {str(e)}")
    except Exception as e:
        print(f"发生意外错误: {str(e)}")
        import traceback
        traceback.print_exc()