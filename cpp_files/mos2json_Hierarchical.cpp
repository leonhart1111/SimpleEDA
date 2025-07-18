#include "mos_AST_Hierarchical.hpp"

// 定义正则表达式
const std::regex keywords_regex(R"(module|input|output|wire|pmos|nmos|endmodule)");
const std::regex identifier_regex(R"([a-zA-Z_][a-zA-Z0-9_]*)");
//暂时无用
const std::regex number_regex(R"(\d+)");
const std::regex operator_regex(R"([,\.\(\)])");
const std::regex whitespace_regex(R"([ \t\n;]+)");

using Token=std::pair<std::string,int>;

class Lexer {
public:
    Lexer(std::ifstream& f) : curLine(1),file(std::move(f)) {}
    Token pairCurToken(){
        Token token;int type;

        if (std::regex_match(current_token, keywords_regex)){
            type = KEYWORD;
        }
        else if (std::regex_match(current_token, identifier_regex)){
            type = USER_DEF;
        }

        token=std::make_pair(current_token,type);
        current_token.clear();
        
        return token;
    }
    std::string getLine(){
        return std::to_string(curLine);
    }
    Token getNextToken(){
        if(nextToken.first!=""){
            auto token=nextToken;
            nextToken.first="";
            return token;
        }
        // 逐个字符匹配,按顺序添加到词列表
        char c;
        while (file.get(c)) {
            if (c == ',' || c == '(' || c == ')'||c==';') {
                if (!current_token.empty()) {
                    nextToken=std::make_pair(std::string(1, c),SYMBOL);
                    return pairCurToken();
                }
                else{
                    return std::make_pair(std::string(1, c),SYMBOL);
                }
            } 
            else if (c==' '||c=='\n'||c=='\t'||c=='\r'||c=='\v') {
                if(c=='\n'||c=='\r'){
                    curLine++;
                }
                if (!current_token.empty()) {
                    return pairCurToken();
                }
            } 
            else {
                current_token += c;
            }
        }
        if (!current_token.empty()) {
            return pairCurToken();
        }
        else return std::make_pair("",NONE);
    }

private:
    std::string current_token;
    Token nextToken;//under analysis
    std::ifstream file;
    int curLine;
    // std::vector<Token> tokens;
    // size_t pos;
};

json MosNode::toJSON() const{
    json j;
    j["type"] = (type == PMOS) ? "pmos" : "nmos";
    //j["name"] = name;
    j["drain"] = drain;
    j["source"] = source;
    j["gate"] = gate;
    return j;
}
json PortNode::toJSON() const{
    json j;
    j["type"] = type;
    //j["name"] = name;
    for(auto&i:in){
        j["in"].push_back(i->name);
    }
    for(auto&o:out){
        j["out"].push_back(o->name);
    }
    return j;
}

// 实现SubModuleNode的toJSON方法
json SubModuleNode::toJSON() const {
    json j;
    j["module"] = module_name;
    j["parameters"] = parameters;
    return j;
}

json ModuleNode::toJSON() const{
    json j;
    json port_j;
    json mos_j;
    json sub_j; // 添加子模块JSON对象
    
    j["type"]="module";
    j["name"]=name;
    
    // 添加端口信息
    for(const auto&port:ports){
        port_j[port->name]=port->toJSON();
    }
    
    // 添加晶体管信息
    for (const auto& mosfet : mosfets) {
        mos_j[mosfet->name]=mosfet->toJSON();
    }
    
    // 添加子模块信息
    for (const auto& submodule : subModules) {
        sub_j[submodule->name] = submodule->toJSON();
    }
    
    j["ports"]=port_j;
    j["mosfets"]=mos_j;
    j["subModules"] = sub_j; // 添加子模块到主JSON
    
    return j;
}

class Parser{
private:
    Lexer& lexer;
    Token token;//under analysis
    int pcount,ncount;
    std::shared_ptr<ModuleNode> moduleNode;
    std::vector<std::shared_ptr<ModuleNode>> modules;
public:
    Parser(Lexer& lexer):lexer(lexer),pcount(1),ncount(1){
        resetModule();
        moduleNode = std::make_shared<ModuleNode>();
    }
    void parse(){
        while((token=lexer.getNextToken()).second!=NONE){
            if(token.first=="module"){
                parseModule();
            }
            if(token.first=="endmodule"){
                modules.push_back(moduleNode);
                resetModule();
                //分析新定义moduleNode
                moduleNode = std::make_shared<ModuleNode>();
            }
        }
    }
    json toJSON() const {
        json module_j;
        for(const auto&m:modules){
            module_j[m->name]=m->toJSON();
        }
        return module_j;
    }
    std::vector<std::shared_ptr<ModuleNode>> getModules() const {
        return modules;
    }
private:
    void parseModule(){
        moduleNode->name = lexer.getNextToken().first;
        //TODO:删除无用port
        auto vcc=std::make_shared<PortNode>();
        auto gnd=std::make_shared<PortNode>();
        vcc->name = "VCC";
        gnd->name = "GND";
        vcc->type = POWER;
        gnd->type = POWER;
        moduleNode->ports.push_back(vcc);
        moduleNode->ports.push_back(gnd);

        expect("(");
        while((token=lexer.getNextToken()).first!=")")
        {
            if(token.second==USER_DEF){
                auto portNode=std::make_shared<PortNode>();
                portNode->name = token.first;
                moduleNode->ports.push_back(portNode);
            }
            else if(token.first==","){
                continue;
            }
            else{
                throw std::runtime_error("Error:module中语法错误,Line "+lexer.getLine());
            }
        }
        while ((token = lexer.getNextToken()).first != "endmodule") {
            if (token.first == "input" || token.first == "output"|| token.first == "wire") {
                parsePort(token.first);
            }
            else if (token.first == "pmos" || token.first == "nmos") {
                parseMos(token.first);
            } 
            else if (token.first == "//"){
                parseNotes();
            }
            else if (token.second == USER_DEF){
                parseModuleNesting(token.first);
            }
            else if( token.second==NONE){
                throw std::runtime_error("Error:缺少endmodule,Line "+lexer.getLine());
            }
        }
        removeEmptyPort();
        AddPuts();
    }
    void parsePort(const std::string type){
        //需要分号h
        while((token=lexer.getNextToken()).first!=";"){
            if(token.second == USER_DEF){
                if(type== "wire"){
                    bool repeat_def_wire=false;
                    for (auto& port : moduleNode->ports) {
                        if (port->name == token.first && port->type==WIRE) {
                            std::cout<<"Warning:"<<"定义的wire类型中存在重复名称,Line "+lexer.getLine()<<std::endl;
                            repeat_def_wire=true;
                        }
                        else if (port->name == token.first && port->type==POWER) {
                            throw std::runtime_error("Error:VCC,GND是保留关键字,Line "+lexer.getLine());
                        }
                        else if (port->name == token.first && (port->type==INPUT || port->type==OUTPUT)){
                            throw std::runtime_error("Error不允许把输入/输出端口重定义为wire,Line "+lexer.getLine());
                        }
                    }
                    // 跳过重复定义
                    if(!repeat_def_wire){
                        auto wireNode=std::make_shared<PortNode>();
                        wireNode->name = token.first;
                        wireNode->type = WIRE; 
                        moduleNode->ports.push_back(wireNode);
                    }
                }
                else {
                    bool finded_port = false;
                    for (auto& port : moduleNode->ports) {
                        if (port->name == token.first) {
                            finded_port = true;
                            if(type == "input" || type == "output"){
                                if(port->type==POWER){
                                    throw std::runtime_error("Error:VCC,GND是保留关键字,Line "+lexer.getLine());
                                }
                                else if(port->type != UNDEF){
                                    throw std::runtime_error("Error:对端口类型的重复定义,Line "+lexer.getLine());
                                }
                                port->type = type == "input" ? INPUT : OUTPUT;
                            }
                            else{
                                throw std::runtime_error("Error端口类型错误,Line "+lexer.getLine());
                            }
                            break; // Exit the loop once the port is found and rewritten
                        }
                    }
                    if(!finded_port){
                        throw std::runtime_error("Error:声明的输入/输出端口未在module上定义,Line "+lexer.getLine());
                    }
                }
            }
            else if(token.first==","){
                continue;
            }
            else if(token.second == KEYWORD){
                throw std::runtime_error("Error:端口名不能为关键字,Line "+lexer.getLine());
            }
            else{
                throw std::runtime_error("Error:端口定义语法错误,Line "+lexer.getLine());
            }
        }
    }
    void parseMos(const std::string type){
        // Mos mos;
        moduleNode->mosfets.push_back(std::make_shared<MosNode>());
        auto mosNode=moduleNode->mosfets[moduleNode->mosfets.size()-1];
        mosNode->type=(type=="pmos")?PMOS:NMOS;
        mosNode->name = (type=="pmos")?"p"+std::to_string(pcount++):"n"+std::to_string(ncount++);

        expect("(");
        mosNode->drain = lexer.getNextToken().first;
        expect(",");
        mosNode->source = lexer.getNextToken().first;
        expect(",");
        mosNode->gate = lexer.getNextToken().first;
        
        expect(")");
        expect(";");
        int def_port = 0;
        for(auto&p:moduleNode->ports){
            if(p->name==mosNode->drain||p->name==mosNode->source||p->name==mosNode->gate){
                def_port++;
            }
        }
        if(def_port<3){
            throw std::runtime_error("Error:语句中有未定义的端口名,Line "+lexer.getLine());
        }
        
        for(auto&port:moduleNode->ports){
            if(port->name == mosNode->drain){
                port->in.push_back(mosNode);
                mosNode->_drain=port;
            }
            if(port->name == mosNode->source){
                port->out.push_back(mosNode);
                mosNode->_source=port;
            }
            if(port->name == mosNode->gate){
                port->out.push_back(mosNode);
                mosNode->_gate=port;
            }
        } 
    }
    void parseNotes(){
        do{
            token=lexer.getNextToken();
            if( token.second==NONE){
                throw std::runtime_error("Error:注释末尾必须加分号,Line "+lexer.getLine());
            }
        }while(token.first!=";" && token.first!=")" && token.first!="endmodule");
    }
    void parseModuleNesting(const std::string subModuleName){
        //必须在modules中已有定义
        bool found=false;
        std::vector<std::string> paras;//参数集
        Token instanceToken = lexer.getNextToken();
        if(instanceToken.second != USER_DEF){
            throw std::runtime_error("Error: Expected instance name after module name, Line " + lexer.getLine());
        }
        for(auto&m:modules){
            if(m->name==subModuleName){
                auto subModuleNode = std::make_shared<SubModuleNode>();
                // 设置子模块信息
                subModuleNode->module_name = subModuleName; // 记录模块名
                subModuleNode->name = instanceToken.first;  // 实例名
                
                // auto it = std::find_if(moduleNode->subModules.begin(),moduleNode->subModules.end(),[&subModuleName](const std::shared_ptr<ModuleNode>& subM){
                //     return subM->name == subModuleName;
                // });
                //添加子模块定义
                // if(it == moduleNode->subModules.end()){
                moduleNode->subModules.push_back(subModuleNode);
                //moduleNode->subModuleCount++;
                //收集参数
                expect("(");
                while((token=lexer.getNextToken()).first!=")"){
                    if(token.second==USER_DEF){
                        paras.push_back(token.first);
                    }
                    else if(token.first==","){
                        continue;
                    }
                    else{
                        throw std::runtime_error("Error:实例化语法错误,Line "+lexer.getLine());
                    }
                }
                // 保存参数
                subModuleNode->parameters = paras; // 记录参数列表
                
                expect(";");
                int putSize=0;
                for(auto&p:m->ports){
                    if(p->type==INPUT || p->type==OUTPUT){
                        putSize++;
                    }
                }
                if(paras.size()!=putSize){
                    throw std::runtime_error("用于实例化的参数数量错误,Line "+lexer.getLine());
                }
                //加入内部端口
                for(auto&p:m->ports){
                    if(p->type!=INPUT && p->type!=OUTPUT && p->type!=POWER){
                        auto subPortNode = std::make_shared<PortNode>();
                        subPortNode->name = instanceToken.first + "." + p->name;
                        subPortNode->type = WIRE;
                        moduleNode->ports.push_back(subPortNode);
                        //加入子模块中
                        subModuleNode->wirePorts.push_back(subPortNode);
                    }
                }
                //加入晶体管
                for(auto mos:m->mosfets){
                    //提前定义
                    moduleNode->mosfets.push_back(std::make_shared<MosNode>());
                    auto subMosNode = moduleNode->mosfets[moduleNode->mosfets.size()-1];

                    subMosNode->type = mos->type;
                    subMosNode->name = instanceToken.first + "." + mos->name;
                    subMosNode->drain = instanceToken.first + "." + mos->drain;
                    subMosNode->source =  instanceToken.first + "." +mos->source;
                    subMosNode->gate = instanceToken.first + "." + mos->gate;
                    int def_port = 0;
                    int put_seq = 0;
                    for(auto&p:m->ports){  
                        // 特殊处理：输入输出端口设定为参数值
                        if(p->type == INPUT || p->type == OUTPUT){
                            auto wrongPortName = instanceToken.first + "." + p->name;
                            if(wrongPortName == subMosNode->drain){
                                subMosNode->drain = paras[put_seq];
                            }
                            if(wrongPortName == subMosNode->source){
                                subMosNode->source = paras[put_seq];
                            }
                            if(wrongPortName == subMosNode->gate){
                                subMosNode->gate = paras[put_seq];
                            }
                            put_seq++;
                        }
                        // 特殊处理：power对象设定为默认值
                        if(p->type == POWER){
                            auto wrongPortName = instanceToken.first + "." + p->name;
                            if(wrongPortName == subMosNode->drain){
                                subMosNode->drain = p->name;
                            }
                            if(wrongPortName == subMosNode->source){
                                subMosNode->source = p-> name;
                            }
                            if(wrongPortName == subMosNode->gate){
                                subMosNode->gate = p->name;
                            }
                        }
                        
                    }
                    for(auto&p:moduleNode->ports){  
                        if(p->name==subMosNode->drain||p->name==subMosNode->source||p->name==subMosNode->gate){
                            def_port++;
                        }
                    }
                    if(def_port<3){
                        throw std::runtime_error("Error:语句中有未定义的端口名,Line "+lexer.getLine());
                    }
                    for(auto&port:moduleNode->ports){
                        if(port->name == subMosNode->drain){
                            port->in.push_back(subMosNode);
                            subMosNode->_drain=port;
                        }
                        if(port->name == subMosNode->source){
                            port->out.push_back(subMosNode);
                            subMosNode->_source=port;
                        }
                        if(port->name == subMosNode->gate){
                            port->out.push_back(subMosNode);
                            subMosNode->_gate=port;
                        }
                    }
                    // 加入子模块中
                    subModuleNode->mosfets.push_back(subMosNode);
                }
                int iop_index=0;
                auto iop=m->ports[iop_index];
                while(iop->type!=INPUT&&iop->type!=OUTPUT){
                    iop=m->ports[++iop_index];
                }
                // 加入输入输出端口映射关系
                for(int i=0;i<paras.size();++i){
                    // 在模块端口中找到参数值
                    for(auto&p:moduleNode->ports){
                        if(p->name == paras[i]){  
                            p->belongTo=subModuleNode;
                            if(iop->type==INPUT){
                                subModuleNode->inputPorts.push_back(p);
                                break;
                            }
                            else if(iop->type==OUTPUT){
                                subModuleNode->outputPorts.push_back(p);
                                break;
                            }
                        }
                    }
                    iop=m->ports[++iop_index];
                }
                found=true;
                break;
            }
            
        }
        if(found){
            ;
        }
        else{
            throw std::runtime_error("Error:未定义的模组被实例化,Line "+lexer.getLine());
        }
    }
    // 只接受期望的Token
    void expect(const std::string& expectedToken) {
        token = lexer.getNextToken();
        if (token.first != expectedToken) {
            throw std::runtime_error("Expected \"" + expectedToken + "\", but got \"" + token.first+"\",Line "+lexer.getLine());
        }
    }
    // 删除没有连接对象的端口：1.VCC和GND未使用 2.用户定义了未使用的端口
    void removeEmptyPort(){
        std::vector<std::shared_ptr<PortNode>> to_remove;
        // 收集需要删除的元素
        for (const auto& port : moduleNode->ports) {
            if (port != nullptr && port->in.empty() && port->out.empty()) {
                if(port->type!=POWER){
                    std::cout<<"Warning:定义的端口未使用-"<<port->name<<",Line "+lexer.getLine()<<std::endl;
                }
                to_remove.push_back(port);
            }
        }
        // 删除收集到的元素
        for (const auto& port : to_remove) {
            moduleNode->ports.erase(
                std::remove(moduleNode->ports.begin(), moduleNode->ports.end(), port),
                moduleNode->ports.end()
            );
        }
    }
    void AddPuts(){
        int putCount=0;
        for(auto&p:moduleNode->ports){
            if(p->type==INPUT){
                moduleNode->inputs.push_back(p);
            }
            else if(p->type==OUTPUT){
                moduleNode->outputs.push_back(p);
            }
            else if(p->type==WIRE){
                break;
            }
        }
    }
    // 分析新模组前的重置
    void resetModule(){
        pcount=1;
        ncount=1;
    }
};
// TODO：采用字节缓冲读取方法
// TODO：采用Parser实时读取方法 DONE
// PROBLEM: 采用保证不变的电路仿真是否可行


// int main(int argc, char* argv[]){
//     // 检查是否提供了文件名
//     std::string input_file = argv[1];
//     // std::string input_file="adders.v";
//     std::ifstream file(input_file);
//     std::ofstream output_file(std::string(input_file)+".json");
//     if(!file.is_open()){
//         std::cout << "文件打开失败" << std::endl;
//         exit(1);
//     }
//     Lexer lexer(file);
//     Parser parser(lexer);
//     parser.parse();
//     json ast=parser.toJSON();

//     for (auto& i : parser.getModules()) {
//         std::cout << "module " << i->name << std::endl;
//         // printf("module %s\n", i->name);
//         i->simulate_all();
//         std::cout << "\n";
//     }

//     output_file<<ast.dump(4);

//     output_file.close();
//     file.close();
// }

void options_helper() {
    std::cout << "You can use the following options\n";
    std::cout << "-h (help): 命令行选项实用信息\n";
    std::cout << "-f (file) <addr>: 需解析的文件路径\n";
    std::cout << "-s (shell): 在终端打印真值表\n";
    std::cout << "-m (markdown): 将真值表打印到md文件\n";
    std::cout << "-c (conversation): 交互式查询\n";
    std::cout << "-d (dump): 解析并输出json文件\n";
    exit(0);
}

int main(int argc, char* argv[]){
    std::map<std::string, std::string> options;
    if (argc == 1) {
        options_helper();
        return 0;
    }
    for (int i = 1; i < argc; i++) {
        std::string param(argv[i]);
        if (param[0] == '-') {
            if (param == "-h") {
                options_helper();
            } else if (param == "-f") {
                if (i != argc - 1) options[param] = argv[++i];
                else options_helper();
            } else if (param == "-m" || param == "-s" || param == "-c" || param == "-d") {
                options[param] = "";
            }
        } else {
            options_helper();
        }
    }

    for (auto& pair : options) {
        std::cout << pair.first << ": " << pair.second << "\n";
    }

    if (options.count("-f") == 0) {
        options_helper();
    }
    // 检查是否提供了文件名
    std::string input_file = options["-f"];
    std::ifstream file(input_file);

    // 读入文件相关
    if(!file.is_open()){
        std::cout << "fail to open " << options["-f"] << std::endl;
        exit(1);
    }
    Lexer lexer(file);
    Parser parser(lexer);
    parser.parse();
    json ast=parser.toJSON();
    file.close();

    if (options.count("-d")) {
        std::string dump_name = input_file + ".json";
        std::ofstream output_file(dump_name);
        output_file << ast.dump(4);
        output_file.close();
    }

    if (options.count("-c")) {
        bool loop = true;
        while(loop) {
            std::cout << "Select one module: (enter its index)\n";

            // ASK: return &
            std::vector<std::shared_ptr<ModuleNode>> modules = parser.getModules();
            for (int i = 0; i < modules.size(); i++) {
                std::cout << i + 1 << "." << modules[i]->name << "\t";
            }
            std::cout << "\n";
            
            int idx;
            std::cin >> idx;

            if (idx > 0 && idx <= modules.size()) {
                modules[idx-1]->conversation();
            } else {
                std::cout << "Invalid index\n";
            }
        
            while (1) {
                std::cout << "\n";
                std::cout << "Exit all ? [y/n]\n";
                char c;
                std::cin >> c;
                if (c == 'y') {
                    loop = false;
                    break;
                }
                else if (c == 'n') break;
            }
            
        }
    }
    if (options.count("-m")) {
        std::ofstream md_file(input_file + ".md");
        if (!md_file.is_open()) {
            std::cout << "fail to open " << options["-m"] << std::endl;
            exit(1);
        }
        std::cout << input_file + ".md\n";
        md_file.clear();
        md_file << "# Simulation of " << options["-f"] << "\n"; 
        for (auto& i : parser.getModules()) {
            md_file << "## module " << i->name << "\n";
            i->simulate_all_to_file(md_file);
            md_file << "\n";
        }
        md_file.close();
    }
    if (options.count("-s")) {
        for (auto& i : parser.getModules()) {
            std::cout << "module " << i->name << std::endl;
            i->simulate_all();
            std::cout << "\n";
        }
    }
    return 0;
}