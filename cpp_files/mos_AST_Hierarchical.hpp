#pragma once
#include <iostream>
#include <string>
#include <fstream>
#include <sstream>
#include <vector>
#include <regex>
#include <fstream>
#include <map>
#include <memory>

#include "json.hpp"
using json=nlohmann::ordered_json;

#define UNDEF ""
#define INPUT "input"
#define OUTPUT "output"
#define WIRE "wire"
#define POWER "power"
// enum PortType {
//     UNDEF,
//     INPUT,
//     OUTPUT,
//     WIRE,
//     POWER
// };
enum MosType {
    PMOS,
    NMOS
};
enum TokenType {
    KEYWORD,
    USER_DEF,
    SYMBOL,
    NONE
};
enum STATE{
    ZERO,
    ONE,
    Z,
    X,
    ERROR
};

STATE translate(long long x) {
    if (x == 0) return ZERO;
    else if (x == 1) return ONE;
    throw std::runtime_error("translate fail");
    return X;
}

STATE translate_cin(char c) {
    if (c == '0') return ZERO;
    else if (c == '1') return ONE;
    else if (c == 'Z' || c == 'z') return Z;
    else if (c == 'X' || c == 'x') return X;
    return ERROR;
}

char retranslate(STATE x) {
    switch(x) {
        case ZERO:  return '0';
        case ONE:   return '1';
        case Z:     return 'Z';
        case X:     return 'X';
    }
    throw std::runtime_error("retranslate fail");
}

// 定义AST节点结构
struct ASTNode {
    virtual json toJSON() const = 0;
};
struct PortNode;
struct SubModuleNode;
struct ModuleNode;
struct MosNode:public ASTNode
{
    int type;
    std::string name;
    std::string drain;
    std::string source;
    std::string gate;
    std::shared_ptr<PortNode> _drain;
    std::shared_ptr<PortNode> _source;
    std::shared_ptr<PortNode> _gate;

    json toJSON() const override;

    void trigger();
};

struct PortNode:public ASTNode
{
    std::string type;// = 0;
    std::string name;
    std::vector<std::shared_ptr<MosNode>> in;
    std::vector<std::shared_ptr<MosNode>> out;
    // TODO:一个端口属于多个子模块(这可能吗？)
    std::shared_ptr<SubModuleNode> belongTo;
    
    STATE state;

    json toJSON() const override;

    void trigger(STATE new_state);
};
struct SubModuleNode
{
    std::string name;
    std::string module_name; // 添加模块名
    std::vector<std::string> parameters; // 添加参数列表
    std::vector<std::shared_ptr<PortNode>> inputPorts;
    std::vector<std::shared_ptr<PortNode>> outputPorts;

    std::vector<std::shared_ptr<PortNode>> wirePorts;
    std::vector<std::shared_ptr<MosNode>> mosfets;

    json toJSON() const; // 添加toJSON方法
};
struct ModuleNode : public ASTNode
{
    std::string name;
    std::vector<std::shared_ptr<PortNode>> inputs;
    std::vector<std::shared_ptr<PortNode>> outputs;
    std::vector<std::shared_ptr<PortNode>> ports;
    std::vector<std::shared_ptr<MosNode>> mosfets;
    std::vector<std::shared_ptr<SubModuleNode>> subModules;
    //int subModuleCount=0;

    json toJSON() const override;

    int getInputIndex(const std::string& str) {
        auto it = std::lower_bound(inputs.begin(), inputs.end(), str, 
            [](const std::shared_ptr<PortNode>& node, const std::string& value) {
                return node->name < value;
            }
        );
        if (it != inputs.end() && (*it)->name == str) {
            return std::distance(inputs.begin(), it);
        } else {
            return -1; // 未找到
        }
    }
    void simulate_all_to_file (std::ofstream& file) {
        int input_nums = inputs.size();
        int output_nums = outputs.size();
        long long pow = std::pow(2, input_nums);
        std::vector<STATE> inputs_state(input_nums);
    
        file << "| Inputs ";
        for (int i = 0; i < input_nums; i++) {
            file << "| ";
        }
        file << " Outputs ";
        for (int i = 0; i < output_nums; i++) {
            file << "| ";
        }
        file << "\n";
        file << "|";
        for (int i = 0; i < input_nums + output_nums; i++) {
            file << "---|";
        }
        file << "\n";
        file << "| ";
        for (int i = 0; i < input_nums; i++) {
            file << " " << inputs[i]->name << " |";
        }
        for (int i = 0; i < output_nums; i++) {
            file << " " << outputs[i]->name << " |";
        }
        file << "\n";
        

        for (long long i = 0; i < pow; i++) {
            file << "|";
            // TODO 全部真值
            for (int j = 0; j < input_nums; j++) {
                inputs_state[j] = translate((i >> j) & 1);
                file << " " << retranslate(inputs_state[j]) << " |";
            }
            trigger(inputs_state);
            for (int j = 0; j < output_nums; j++) {
                file << " " << retranslate(outputs[j]->state) << " |";
            }
            file << "\n";
        }
    }

    void simulate_all() {
        int input_nums = inputs.size();
        int output_nums = outputs.size();
        long long pow = std::pow(2, input_nums);
        std::vector<STATE> inputs_state(input_nums);

        for (long long i = 0; i < pow; i++) {
            std::cout << "inputs: ";
            for (int j = 0; j < input_nums; j++) {
                inputs_state[j] = translate((i >> j) & 1);
                std::cout << inputs[j]->name << ": " << retranslate(inputs_state[j]) << "\t";
            }
            std::cout << "\n";
            trigger(inputs_state);
            std::cout << "outputs: ";
            for (int j = 0; j < output_nums; j++) {
                std::cout << outputs[j]->name << ": " << retranslate(outputs[j]->state) << "\t";
            }
            std::cout << "\n\n";
        }
    }

    void conversation() {
        std::cout << "Start your requiring: (Enter exit)\n";
        int input_nums = inputs.size();
        std::vector<STATE> inputs_state(input_nums);
        while (1) {
            for (int i = 0; i < input_nums; i++) {
                std::cout << inputs[i]->name << ": ";
                char c;
                std::cin >> c;
                STATE tmp = translate_cin(c);
                if (tmp == ERROR) {
                    std::cout << "Invalid input\n";
                    i--;
                    continue;
                }
                inputs_state[i] = tmp;
            }
            trigger(inputs_state);
            std::cout << "outputs: ";
            for (int j = 0; j < outputs.size(); j++) {
                std::cout << outputs[j]->name << ": " << retranslate(outputs[j]->state) << "\t";
            }
            while (1) {
                std::cout << "\n";
                std::cout << "Exit from module " << name << "? [y/n]\n";
                char c;
                std::cin >> c;
                if (c == 'y') return;
                else if (c == 'n') break;
            }
            std::cout << "\n";
        }
    }

    void trigger(std::vector<STATE>& inputs_state) {
        if (inputs_state.size() != inputs.size()) {
            throw std::runtime_error("inputs size doens't match");
        }
        reset();
        ports[0]->trigger(ONE);
        ports[1]->trigger(ZERO);
        for (int i = 0; i < inputs_state.size(); i++) {
            inputs[i]->trigger(inputs_state[i]);
        }
    }

    void reset() {
        for (int i = 0; i < ports.size(); i++) {
            ports[i]->state = Z;
        }
    }
};


void PortNode::trigger(STATE new_state) {
    // std::cout << "set port " << name << " as " << retranslate(new_state) << "\n";
    if (state == X || state == new_state || new_state == Z) {
        return;
    } else if (state == Z) {
        state = new_state;
    } else {
        state = X;
    }
    for (int i = 0; i < out.size(); i++) {
        out[i]->trigger();
    }
}

void MosNode::trigger() {
    if (_gate->state == Z) return;
    if (_gate->state == X) {
        _drain->trigger(X);
    } else if (type == PMOS) {
        if (_gate->state == ZERO) _drain->trigger(_source->state);
    } else {
        if (_gate->state == ONE) _drain->trigger(_source->state);
    }
}