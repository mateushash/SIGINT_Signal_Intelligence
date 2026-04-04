#include <string>
#include "cyphers/MorseCode.h"

class Worker {
  public:
    //Constructors 
    //Default Values: empty cypher = offline worker
    Worker(bool s=false, std::string cypher="", std::string m=""): online(s), cypherType(cypher), message(m) {}
    Worker(std::string& c, std::string& m): online(true), cypherType(c), message(m) {}
    Worker(std::string& m): message(m) {}
    

    //Cyphers Decryption Modules
    void vigenere(std::string& message);
    void morse(std::string& message);
    void caesar(std::string& message);

    //Get Members
    std::string getCypherType();

  private:
    bool online;
    std::string cypherType;
    std::string message;
};
