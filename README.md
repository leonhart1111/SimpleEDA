# SimpleEDA
- A simple Electronic Design Automation
- 实现可交互式设计、verilog一键式布局布线并预览
### Environment
- python3.9: flask; plotly; flask_cors
- C++: json.hpp(if you want to improve and re-g++ TestRoute.exe&mos2json.exe)
### How to run the project
click app.py or
```cmd
python app.py
```
then click chipdesigner.html (open it by a browser) and edit your chip(or circuit) on the website.
#### Buttons on the top：
- "编写Verilog" is for creating your verilog file and previewing it;
- "选择模式" is for placing the components or moving them by simply click or drag;
- "连线模式" is for create nets by click the pins;
- "进行布局" is for **Layouting and Routing**, all you have to do is wait a few seconds(maybe minutes, due to the size of your  circuit, but I'm confident of its efficiency)
- "导入文件" is for laoding the Layout_after and Route_after files, in fact, there are both of them after click "进行布局". You can also laod your own files.
- "删除模式" is for deleting, simply click one component;
- "显示所有层" is for see all wires no matter which layer they're on;
#### On the left:
- These components are for "选择模式";
- "金属层%d" is for selecting to see wires of which layers;
- Below are infomations of the circuit.
