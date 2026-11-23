/* OFFLINE benchmark adapter only. System zlib/OpenSSL, never a game addon or
 * production decoder. These host timings do not substitute for Forever timing.
 * cc -shared -fPIC -O2 scripts/codec_zlib_offline.c -lz -lcrypto -o /tmp/codec.so
 * Lua 5.1 exports the few API symbols below; no private client library is used. */
#include <stdlib.h>
#include <string.h>
#include <zlib.h>
#include <openssl/evp.h>
typedef struct lua_State lua_State;
extern const char *luaL_checklstring(lua_State *,int,size_t *);
extern int luaL_error(lua_State *,const char *,...);
extern void lua_pushlstring(lua_State *,const char *,size_t);
extern void lua_createtable(lua_State *,int,int);
extern void lua_pushcclosure(lua_State *,int (*)(lua_State *),int);
extern void lua_setfield(lua_State *,int,const char *);
static int decode(lua_State *L) {
    size_t n;const unsigned char *s=(const unsigned char *)luaL_checklstring(L,1,&n);
    if(!n||n>700000||n%4)return luaL_error(L,"offline Base64 input bound");
    unsigned char *out=malloc(n*3/4+1);if(!out)return luaL_error(L,"allocation failed");
    int count=EVP_DecodeBlock(out,s,(int)n);
    if(count<0){free(out);return luaL_error(L,"Base64 refused");}
    if(s[n-1]=='=')count--;if(s[n-2]=='=')count--;
    lua_pushlstring(L,(const char*)out,(size_t)count);free(out);return 1;
}
static int decompress(lua_State *L) {
    size_t n;const char *s=luaL_checklstring(L,1,&n);
    if(!n||n>525000)return luaL_error(L,"offline compressed input bound");
    unsigned char *out=malloc(524289);if(!out)return luaL_error(L,"allocation failed");
    z_stream z;memset(&z,0,sizeof(z));z.next_in=(unsigned char*)s;z.avail_in=(uInt)n;
    z.next_out=out;z.avail_out=524289;
    int status=inflateInit2(&z,-15);if(status==Z_OK)status=inflate(&z,Z_FINISH);
    size_t count=z.total_out;int valid=status==Z_STREAM_END&&z.avail_in==0&&count<=524288;
    inflateEnd(&z);
    if(!valid){free(out);return luaL_error(L,"raw Deflate refused/size bound");}
    lua_pushlstring(L,(const char*)out,count);free(out);return 1;
}
int luaopen_market_codec_offline(lua_State *L) {
    lua_createtable(L,0,2);lua_pushcclosure(L,decode,0);lua_setfield(L,-2,"DecodeBase64");
    lua_pushcclosure(L,decompress,0);lua_setfield(L,-2,"DecompressString");return 1;
}
