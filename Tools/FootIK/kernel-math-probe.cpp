#include <array>
#include <cmath>
#include <limits>
#include <cstdio>
#include <cstdint>
#include <cstring>
namespace ProphecyFootIKMath{namespace ArmKernel{double Max(double,double);double Min(double,double);}namespace EntryKernel{double Max(double,double);double Min(double,double);}namespace LegKernel{double Max(double,double);double Min(double,double);}}
double ReferenceMax(double A,double B){if(std::isnan(A)||std::isnan(B))return std::numeric_limits<double>::quiet_NaN();if(A>B)return A;if(B>A)return B;return A==0?(std::signbit(A)&&std::signbit(B)?-0.:0.):A;}
double ReferenceMin(double A,double B){if(std::isnan(A)||std::isnan(B))return std::numeric_limits<double>::quiet_NaN();if(A<B)return A;if(B<A)return B;return A==0?(std::signbit(A)||std::signbit(B)?-0.:0.):A;}
int main(){using namespace ProphecyFootIKMath;using Fn=double(*)(double,double);const Fn implementations[3][2]={{ArmKernel::Min,ArmKernel::Max},{EntryKernel::Min,EntryKernel::Max},{LegKernel::Min,LegKernel::Max}};const Fn reference[2]={ReferenceMin,ReferenceMax};std::array<double,160> values{};
 const double special[]={0.,-0.,1.,-1.,std::numeric_limits<double>::infinity(),-std::numeric_limits<double>::infinity(),std::numeric_limits<double>::quiet_NaN(),-std::numeric_limits<double>::quiet_NaN(),std::numeric_limits<double>::min(),-std::numeric_limits<double>::min(),std::numeric_limits<double>::denorm_min(),-std::numeric_limits<double>::denorm_min()};
 for(int i=0;i<12;i++)values[i]=special[i];uint64_t state=0x921534fabb03137dull;for(int i=12;i<int(values.size());i++){state=state*6364136223846793005ull+1442695040888963407ull;std::memcpy(&values[i],&state,8);}int checks=0;
 for(const auto& pair:implementations)for(int k=0;k<2;k++)for(double a:values)for(double b:values){const double actual=pair[k](a,b),expected=reference[k](a,b);checks++;if(std::memcmp(&actual,&expected,8)){std::fprintf(stderr,"Mismatch %a %a -> %a / %a\n",a,b,actual,expected);return 1;}}
 std::printf("{\"passed\":true,\"checks\":%d,\"kernels\":3,\"signedZero\":true,\"nonfinite\":true}\n",checks);return 0;}
