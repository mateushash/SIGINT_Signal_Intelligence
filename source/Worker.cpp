#include "Worker.h"


std::string Worker::getCypherType() {
  return this->cypherType;
}


void Worker::morse(std::string& message) {
  MorseCode* morse = new MorseCode();

  morse->decodeMessage(message);
  
} 
