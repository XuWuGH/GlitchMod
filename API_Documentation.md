# Glitch 认证服务器 API 文档

## 服务器信息

- **主机**: `127.0.0.1` (本地) 或服务器IP
- **端口**: `8888`
- **协议**: TCP Socket

---

## 接口列表

### 1. 开放接口 - Token验证

无需登录即可访问的接口，用于验证客户端持有的token是否有效。

#### 请求

```
VERIFY_TOKEN:<token字符串>
```

**示例**:
```
VERIFY_TOKEN:PPSHDH7727aashadhu@ll
```

#### 响应

**验证成功**:
```
TOKEN_VALID
```

**验证失败**:
```
TOKEN_INVALID
```

**错误**:
```
ERROR:<错误信息>
```

#### 工作流程

1. 客户端发送 `VERIFY_TOKEN:<token>`
2. 服务端遍历所有用户的 `info.txt` 文件
3. 对比每个用户的 `Token` 字段
4. 如果匹配成功:
   - 服务端为该用户生成新的随机token（32位字母数字组合）
   - 更新 `info.txt` 中的 `Token` 字段
   - 返回 `TOKEN_VALID`
5. 如果所有用户都不匹配:
   - 返回 `TOKEN_INVALID`

#### 注意事项

- 验证成功后，服务端会自动更新token，客户端无需知道新token
- 此接口仅用于验证客户端持有的token是否有效
- 此接口无需先进行版本验证或登录

---

### 2. 登录流程 - 版本验证

登录的第一步，验证客户端版本是否最新。

#### 请求

```
VERSION:<版本号>
```

**示例**:
```
VERSION:1.0.0
```

#### 响应

**版本正确**:
```
OK
```

**版本过期**:
```
ERROR:此版本已过期
```

#### 工作流程

1. 客户端连接后首先发送版本号
2. 服务端读取 `version` 文件中的 `LAST_VERSION` 字段
3. 对比客户端版本和服务器最新版本
4. 如果版本匹配，返回 `OK`，继续登录流程
5. 如果版本不匹配，返回错误并断开连接

---

### 3. 登录流程 - 用户认证

版本验证通过后，发送用户认证信息。

#### 请求

```
<用户名>-<密码哈希>-<HWID哈希>
```

**格式说明**:
- `用户名`: 用户账号名称
- `密码哈希`: SHA256(密码)，64位十六进制字符串
- `HWID哈希`: SHA256(硬件ID)，64位十六进制字符串

**示例**:
```
Auxiao-6c1585eeae466d70195c6f820d9c251b3dcefe6e2ca7d2360be9df634cffd79d-da3806d16d1493e2587a6475a76a0caa5e26ad0d672b9aaf1182084fe94ebddf
```

#### 响应

**登录成功**:
```json
{
  "status": "success",
  "message": "登录成功，剩余时间: 36900分钟",
  "notice": "测试公告内容",
  "username": "Auxiao"
}
```

**登录失败**:
```
ERROR:<错误信息>
```

可能的错误信息:
- `用户不存在`
- `密码错误`
- `HWID不正确`
- `订阅已到期`
- `账户已被封禁`

#### 验证流程

1. 根据用户名找到 `User/{username}/info.txt`
2. 验证密码哈希（错误直接返回，不验证HWID）
3. 验证HWID哈希
4. 检查剩余时间（`Time` 字段）
5. 检查封禁状态（`Ban:Y` 表示封禁，`N` 表示正常）
6. 全部通过返回成功信息和公告

---

### 4. 登录后接口 - 获取Token

登录成功后，可以获取当前用户的token。

#### 请求

```
GET_TOKEN
```

#### 响应

**成功**:
```
TOKEN:<token字符串>
```

**失败**:
```
ERROR:Token not found
```

---

### 5. 登录后接口 - 登出

断开与服务器的连接。

#### 请求

```
LOGOUT
```

#### 响应

无响应，服务器直接断开连接。

---

## 完整登录流程示例

```
客户端                                  服务端
  |                                       |
  |---- VERSION:1.0.0 ------------------->|
  |                                       |
  |<--- OK -------------------------------|
  |                                       |
  |---- Auxiao-<hash>-<hash> ------------>|
  |                                       |
  |<--- {"status":"success",...} ---------|
  |                                       |
  |---- GET_TOKEN ----------------------->|
  |                                       |
  |<--- TOKEN:PPSHDH7727aashadhu@ll -----|
  |                                       |
  |---- LOGOUT -------------------------->|
  |                                       |
  |<--- [连接断开] ------------------------|
```

---

## Token验证流程示例

```
客户端                                  服务端
  |                                       |
  |---- VERIFY_TOKEN:PPSHDH7727... ------>|
  |                                       |
  |    [服务端遍历所有用户info.txt]        |
  |    [找到匹配的用户]                   |
  |    [生成新token并保存到info.txt]      |
  |                                       |
  |<--- TOKEN_VALID ----------------------|
  |                                       |
  |<--- [连接断开] ------------------------|
```

---

## 用户数据文件格式

### info.txt

```
Record:用户名-密码哈希-HWID哈希
Token:随机令牌
Time:剩余分钟数（或 Lifetime）
Ban:Y（封禁）或 N（正常）
```

**示例**:
```
Record:Auxiao-6c1585eeae466d70195c6f820d9c251b3dcefe6e2ca7d2360be9df634cffd79d-da3806d16d1493e2587a6475a76a0caa5e26ad0d672b9aaf1182084fe94ebddf
Token:PPSHDH7727aashadhu@ll
Time:36900
Ban:N
```

---

## 版本文件格式

### version

```
LAST_VERSION="x.x.x"
```

**示例**:
```
LAST_VERSION="1.0.0"
```

---

## 注意事项

1. **编码**: 所有通信使用 UTF-8 编码
2. **缓冲区大小**: 单次接收最大 1024 字节
3. **超时**: 登录后连接5分钟无操作自动断开
4. **线程安全**: 每个连接在独立线程中处理
5. **Token验证接口**: 是开放接口，无需登录即可访问
6. **Token轮换**: 验证成功后原token立即失效，必须使用新token

---

## 错误处理

所有错误响应都以 `ERROR:` 开头，后跟错误描述。

常见错误:
- `ERROR:此版本已过期` - 客户端版本过旧
- `ERROR:请先发送版本号` - 未发送版本号直接发送登录请求
- `ERROR:请求格式错误` - 登录请求格式不正确
- `ERROR:用户不存在` - 用户名不存在
- `ERROR:密码错误` - 密码哈希不匹配
- `ERROR:HWID不正确` - 硬件ID哈希不匹配
- `ERROR:订阅已到期` - 用户剩余时间为0
- `ERROR:账户已被封禁` - 用户被封禁
- `ERROR:Token not found` - 无法获取用户token
- `ERROR:Unknown command` - 未知的命令

---

## 客户端实现建议

### Token验证实现

```csharp
// 示例代码（C#）
using (TcpClient client = new TcpClient())
{
    await client.ConnectAsync("127.0.0.1", 8888);
    using (NetworkStream stream = client.GetStream())
    {
        // 发送验证请求
        byte[] request = Encoding.UTF8.GetBytes($"VERIFY_TOKEN:{token}");
        await stream.WriteAsync(request, 0, request.Length);

        // 接收响应
        byte[] buffer = new byte[1024];
        int bytesRead = await stream.ReadAsync(buffer, 0, buffer.Length);
        string response = Encoding.UTF8.GetString(buffer, 0, bytesRead).Trim();

        if (response == "TOKEN_VALID")
        {
            Console.WriteLine("Token验证成功");
            // 服务端会自动更新token，客户端无需处理
        }
        else if (response == "TOKEN_INVALID")
        {
            Console.WriteLine("Token无效");
        }
    }
}
```

---

## 安全建议

1. **Token存储**: 客户端应将token存储在安全的位置（如Windows凭据管理器）
2. **Token传输**: 使用TLS/SSL加密通信（生产环境建议）
3. **Token更新**: 服务端在验证成功后会自动更新token，防止token被重复使用
4. **HWID绑定**: 登录时验证硬件ID，防止token被盗用
5. **Rate Limiting**: 建议对开放接口添加请求频率限制

---

## 更新日志

### v1.0.0
- 初始版本
- 支持用户登录认证
- 支持Token验证开放接口
- 支持Token自动轮换
