# **FZMotion-MB-UE** 数据传输操作说明 (**Motar**)

## 使用说明

**Version 1.0.0 2022.09.23**

## <span id="page-1-0"></span>目录

| 目录                              | 2  |
|---------------------------------|----|
| 1 FZMotion                      | 3  |
| 1.1 打开 FZMotionMotar-播放         | 3  |
| 1.2 打开 FZMotionMotar-实时         | 3  |
| 2 MotionBuilder                 | 4  |
| 2.1 配置 IP 地址                    | 4  |
| 2.1.1 链接 wifi 情况-配置 ip 地址       | 4  |
| 2.1.2 链接网线情况-配置 IP 地址           | 5  |
| 两台电脑链接网线情况下需要配置相同 ip 地址         | 5  |
| 2.2MotionBuilder 操作             | 8  |
| 2.2.1 导入 LUSTER-Skeleton Device | 8  |
| 2.2.2 导入 UE-LiveLink            | 8  |
| 2.2.3 打开 MotionBuilder          | 10 |
| 3 UE                            | 12 |
| 4 livelink 插件配置                 | 14 |
| 4.1 查看 pc 端 wifi 的 ip 地址        | 14 |
| 4.2 配置 LiveLinkFace             | 15 |

## <span id="page-2-0"></span>**1 FZMotion**

## <span id="page-2-1"></span>**1. 1 打开 FZMotionMotar-播放[1](#page-2-3)**

![](_page_2_Picture_2.jpeg)

- 1) 点击播放按钮
- 2) 点击工程文件
- 3) 选择播放文件
- 4) 点击开始传输按钮
- 5) 观察系统消息窗口看见开始发送数据

## <span id="page-2-2"></span>**1.2 打开 FZMotionMotar-实时**

![](_page_2_Figure_9.jpeg)

<span id="page-2-3"></span>

![](_page_3_Figure_0.jpeg)

- 1) 点击工程
- 2) 点击工程文件
- 3) 点击播放按钮
- 4) 点击开始传输按钮
- 5) 观察系统消息窗口看见开始发送数据

## <span id="page-3-0"></span>**2 MotionBuilder**

### <span id="page-3-1"></span>**2.1 配置 IP 地址**

## <span id="page-3-2"></span>**2.1.1 链接 wifi 情况-配置 ip 地址**

A. 两台电脑链接同一 wifi 情况下可直接在 MotionBuilder 里配置 ip 地址

![](_page_3_Figure_10.jpeg)

- B. 两台电脑链接 wifi 情况-在 Setup 窗口下输入 Address
- 1) 勾选 Use Network Server
- 2) 点击 Online 直至变绿
- 3) 勾选 Live
- 4) 在 Model binding 下点击 Create
- 5) 点击 Setup 下的 Characterize 按钮

## <span id="page-4-0"></span>**2.1.2 链接网线情况-配置 IP 地址**

#### <span id="page-4-1"></span>**两台电脑链接网线情况下需要配置相同 ip 地址**

A. 点击网络和 Internet 设置

![](_page_4_Picture_9.jpeg)

B. 点击更改适配器选项

![](_page_4_Picture_11.jpeg)

C. 选择一个以太网双击

![](_page_5_Picture_0.jpeg)

#### D. 点击属性按钮

![](_page_5_Figure_2.jpeg)

E. 点击 Internet 协议版本 4(TCP/IPv4)

![](_page_6_Figure_0.jpeg)

F. 点击使用下面的 IP 地址设置 IP 地址

![](_page_6_Picture_2.jpeg)

## <span id="page-7-0"></span>**2.2MotionBuilder 操作**

## <span id="page-7-1"></span>**2.2.1 导入 LUSTER-Skeleton Device**

#### 解压文件

![](_page_7_Picture_3.jpeg)

将所有文件拷贝到 MotionBuilder 的安装目录下。例如:C:\Program Files\Autodesk\MotionBuilder 2020\bin\x64\plugins

### <span id="page-7-2"></span>**2.2.2 导入 UE-LiveLink**

#### 解压文件到任意文件夹

![](_page_7_Figure_7.jpeg)

#### A. 打开 MotionBuilder,点击 setting

![](_page_7_Picture_9.jpeg)

#### B. 选择 Preference

![](_page_7_Picture_11.jpeg)

C. 点击 Help,选择 Local Computer/Met..,点击 Browse

![](_page_8_Picture_0.jpeg)

D. 选择刚才解压的文件夹里点击对应 Motion Builder 版本的插件,点击确定。

![](_page_8_Figure_2.jpeg)

## <span id="page-9-0"></span>**2.2.3 打开 MotionBuilder**

![](_page_9_Picture_1.jpeg)

- A. 点击右下窗口的 Assert Browser
- B. 点击 Templates 下的 Devices
- C. 拖拽 LUSTER-Skeleton Device 到 Viewer 区域
- D. 导入 UE4 模型文件至 MotionBuilder
- 1) 在文件夹中寻找 UE4\_Mannequin\_Skeleton\_Sequence\_PreviewMesh-T.fbx 文件拖拽到 Viewer 区域中,选择 FBXmerge 后点击 no animation

![](_page_9_Figure_7.jpeg)

2) 在 Character Controls 窗口中设置 Character 和 Source

![](_page_10_Figure_0.jpeg)

3) 拖拽 UE-LiveLink

![](_page_10_Figure_2.jpeg)

4) 在 Subject Selector 添加 root 设置后点击 Online

![](_page_10_Figure_4.jpeg)

5) 待 Online 变绿后,在 Navigator 左边窗口下拉找到 System,双击 System,勾选 Always refresh viewer

![](_page_11_Figure_0.jpeg)

6) 至此 MotionBuilder 配置完成

## <span id="page-11-0"></span>**3 UE**

1) 双击选择一个关卡

![](_page_11_Figure_4.jpeg)

2) 点击窗口按钮找到实时链接

![](_page_11_Figure_6.jpeg)

#### 3) 点击+源,点击消息总线源选择其中一个源类型

![](_page_12_Picture_1.jpeg)

![](_page_12_Figure_2.jpeg)

#### 4) 点击运行

![](_page_12_Figure_4.jpeg)

#### 5) 运行结果展示

![](_page_13_Picture_0.jpeg)

## <span id="page-13-0"></span>**4 livelink 插件配置**

## <span id="page-13-1"></span>**4.1 查看 pc 端 wifi 的 ip 地址**

![](_page_13_Figure_3.jpeg)

![](_page_14_Picture_0.jpeg)

![](_page_14_Picture_1.jpeg)

- A. 点击网络和 Internet 设置
- B. 点击更改适配器选项
- C. 双击 WLAN
- D. 点击详细信息
- E. 查看 IPv4 地址

## <span id="page-14-0"></span>**4.2 配置 LiveLinkFace**

1) 准备一台苹果 X 及以上的 iphone 手机,在苹果商店下载 LiveLinkFace 这 App

![](_page_15_Picture_0.jpeg)

2) 打开 APP 在左上角设置->

![](_page_15_Picture_2.jpeg)

![](_page_15_Figure_4.jpeg)

4) 添加目标,将当前电脑的局域网 IP 地址输入,其他设置可以不用管