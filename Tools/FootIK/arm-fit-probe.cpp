#include "ProphecyFootIKArmKernel.h"
#include <windows.h>
#include <array>
#include <vector>
#include <fstream>
#include <cstdio>
#include <cstring>
#include <cstdint>
#include <cmath>
#include <chrono>

int main(int argc,char** argv)
{
    if(argc<2){std::fputs("arm-fit-probe fixture.bin [result.bin]\n",stderr);return 2;}
    std::ifstream input(argv[1],std::ios::binary);char magic[8];uint32_t count;uint16_t inputs,outputs;
    input.read(magic,8);input.read(reinterpret_cast<char*>(&count),4);input.read(reinterpret_cast<char*>(&inputs),2);input.read(reinterpret_cast<char*>(&outputs),2);
    if(!input||std::memcmp(magic,"FIKARM01",8)||inputs!=96||outputs!=34||count>100000){std::fputs("Invalid fixture header\n",stderr);return 2;}
    std::vector<std::array<double,130>> records(count);input.read(reinterpret_cast<char*>(records.data()),count*130*sizeof(double));if(!input){std::fputs("Truncated fixture\n",stderr);return 2;}
    std::ofstream result;if(argc>2){result.open(argv[2],std::ios::binary);result.write("FIKRES01",8);result.write(reinterpret_cast<char*>(&count),4);result.write(reinterpret_cast<char*>(&outputs),2);uint16_t zero=0;result.write(reinterpret_cast<char*>(&zero),2);}
    const auto start=std::chrono::steady_clock::now();uint64_t differences=0;double maxError=0;int firstRecord=-1,firstField=-1;
    FILETIME created,exited,kernel,user;auto ticks=[](FILETIME t){return (uint64_t(t.dwHighDateTime)<<32)|t.dwLowDateTime;};GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);const uint64_t cpuStart=ticks(kernel)+ticks(user);
    for(uint32_t i=0;i<count;++i){double actual[34];const double* expected=records[i].data()+96;
        if(!ProphecyFootIKMath::ArmFit(records[i].data(),96,actual,34)){std::fprintf(stderr,"Kernel rejected record %u\n",i);return 3;}
        if(result.is_open())result.write(reinterpret_cast<char*>(actual),sizeof(actual));
        for(int j=0;j<34;++j)if(std::memcmp(&actual[j],&expected[j],sizeof(double))){++differences;maxError=std::fmax(maxError,std::abs(actual[j]-expected[j]));if(firstRecord<0){firstRecord=int(i);firstField=j;}if(differences<=12)std::fprintf(stderr,"record=%u field=%d actual=%.17g expected=%.17g hex=%a / %a\n",i,j,actual[j],expected[j],actual[j],expected[j]);}
    }
    GetThreadTimes(GetCurrentThread(),&created,&exited,&kernel,&user);const double cpuMs=(ticks(kernel)+ticks(user)-cpuStart)/10000.;
    const double wallMs=std::chrono::duration<double,std::milli>(std::chrono::steady_clock::now()-start).count();
    std::printf("{\"passed\":%s,\"records\":%u,\"doubles\":%u,\"differentBits\":%llu,\"maxError\":%.17g,\"firstRecord\":%d,\"firstField\":%d,\"cpuMs\":%.6f,\"wallMs\":%.6f}\n",differences?"false":"true",count,count*34,(unsigned long long)differences,maxError,firstRecord,firstField,cpuMs,wallMs);return differences?1:0;
}
