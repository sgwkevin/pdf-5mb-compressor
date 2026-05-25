# PDF 5MB 自动压缩工具

团队网页版 PDF 压缩工具：上传 PDF，后端自动多档压缩，尽量输出到 5MB 以内并返回下载。

## 功能

- 拖拽或点击上传 PDF
- 自动尝试清晰、标准、强压缩、极限压缩
- 成功后直接下载压缩后的 PDF
- 处理完成后自动清理服务器临时文件
- 默认上传上限 120MB，可通过环境变量调整

## 本地运行

本地需要安装 Docker：

```bash
docker build -t pdf-5mb-compressor .
docker run --rm -p 8000:8000 pdf-5mb-compressor
```

打开：

```text
http://localhost:8000
```

## 部署到 Render

1. 把本项目上传到 GitHub。
2. 打开 Render，选择 New Web Service。
3. 连接 GitHub 仓库。
4. Environment 选择 Docker。
5. 部署完成后，Render 会生成一个公开网址，团队成员打开即可使用。

仓库里已经包含 `render.yaml`，Render 也可以直接按配置部署。

## 环境变量

| 变量 | 默认值 | 说明 |
|---|---:|---|
| `TARGET_MB` | `5` | 目标压缩大小，单位 MB |
| `MAX_UPLOAD_MB` | `120` | 最大上传文件大小，单位 MB |

## 注意

不是所有 PDF 都能保证压到 5MB 以内。  
如果 PDF 页面很多、图片很多、扫描图分辨率很高，即使极限压缩也可能超过 5MB，这时建议拆分 PDF 或先降低原图清晰度。

