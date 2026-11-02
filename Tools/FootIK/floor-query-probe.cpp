#include "ProphecyFootIKFloorKernel.h"
#include <windows.h>
#include <vector>
#include <fstream>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <chrono>

int main(int argc,char** argv)
{
 if(argc<2)return 2;
 std::ifstream file(argv[1],std::ios::binary);char magic[8];uint32_t count;uint16_t unused[2];
 file.read(magic,8);file.read(reinterpret_cast<char*>(&count),4);file.read(reinterpret_cast<char*>(unused),4);
 if(!file||std::memcmp(magic,"FIKFLR01",8)||count>100000)return 2;
 struct Record{std::vector<double> input,expected;};std::vector<Record> records(count);
 for(auto& r:records){uint32_t n,m;file.read(reinterpret_cast<char*>(&n),4);file.read(reinterpret_cast<char*>(&m),4);if(!file||n>1000000||m>10000)return 2;r.input.resize(n);r.expected.resize(m);file.read(reinterpret_cast<char*>(r.input.data()),n*8);file.read(reinterpret_cast<char*>(r.expected.data()),m*8);if(!file)return 2;}
 FILETIME created,exited,kernel,user;auto ticks=[](FILETIME t){return (uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime;};GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);const auto cpuStart=ticks(kernel)+ticks(user);const auto start=std::chrono::steady_clock::now();
 uint64_t differences=0,doubles=0;double maxError=0;
 for(uint32_t i=0;i<count;i++){auto& r=records[i];std::vector<double> actual(r.expected.size());if(!ProphecyFootIKMath::TerrainFloor(r.input.data(),int(r.input.size()),actual.data(),int(actual.size()))){std::fprintf(stderr,"rejected %u\n",i);return 3;}doubles+=actual.size();for(size_t j=0;j<actual.size();j++)if(std::memcmp(&actual[j],&r.expected[j],8)){differences++;maxError=std::fmax(maxError,std::abs(actual[j]-r.expected[j]));if(differences<=12)std::fprintf(stderr,"record=%u field=%zu actual=%.17g expected=%.17g hex=%a/%a\n",i,j,actual[j],r.expected[j],actual[j],r.expected[j]);}}
 GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);double cpuMs=(ticks(kernel)+ticks(user)-cpuStart)/10000.,wallMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
 std::printf("{\"passed\":%s,\"records\":%u,\"doubles\":%llu,\"differentBits\":%llu,\"maxError\":%.17g,\"cpuMs\":%.6f,\"wallMs\":%.6f}\n",differences?"false":"true",count,(unsigned long long)doubles,(unsigned long long)differences,maxError,cpuMs,wallMs);return differences?1:0;
}
