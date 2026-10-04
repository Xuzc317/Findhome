import { Modal } from "antd";
import { useState } from "react";

// 本地工具版本：禁用小程序提示，因为我们有自己的 Web 界面
export default function MobileModal() {
  const [open, setOpen] = useState(false);
  return (
    <Modal
      open={open}
      onCancel={() => {
        setOpen(false);
      }}
      width={"100%"}
      footer={null}
      onClose={() => {
        setOpen(false);
      }}
    >
      <div className="flex flex-col items-center">
        <div className="text-xl font-bold">系统提示</div>
        <div className="text-base flex flex-col items-center gap-2 text-gray-600 mt-2">
          <p>本地租房搜索工具</p>
          <p>建议使用 PC 浏览器获得最佳体验</p>
        </div>
      </div>
    </Modal>
  );
}
