#include <map>
#include <string>

class MorseCode {
  public:
  std::map<char, unsigned int> MORSE_CODE_TABLE = {
    {'a',  0b101},    
    {'b',  0b11000},
    {'c',  0b11010},
    {'d',  0b1100},
    {'e',  0b10},
    {'f',  0b10010},
    {'g',  0b1110},
    {'h',  0b10000},
    {'i',  0b100},
    {'j',  0b10111},
    {'k',  0b1101},
    {'l',  0b10100},
    {'m',  0b111},
    {'n',  0b110},
    {'o',  0b1111},
    {'p',  0b10110},
    {'q',  0b11101},
    {'r',  0b1010},
    {'s',  0b1000},
    {'t',  0b11},
    {'u',  0b1001},
    {'v',  0b10001},
    {'w',  0b1011},
    {'x',  0b11001},
    {'y',  0b11011},
    {'z',  0b11100}
  };

  std::string decodeMessage(std::string m);
  private:
};
