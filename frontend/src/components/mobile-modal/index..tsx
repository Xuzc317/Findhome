import { Modal } from "antd";
import { useState } from "react";

export default function MobileModal() {
  const [open, setOpen] = useState(() => {
    const ua = navigator.userAgent;
    let isMobile =
      /Mobile|Android|webOS|iPhone|iPad|iPod|BlackBerry|IEMobile|Opera Mini/i
        .test(ua);
    if (isMobile) {
      return true;
    }
    return window.innerWidth < 768;
  });
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
        <img src="/images/ewm.jpg" className="w-[220px] mt-4" />
        <div className="text-base flex flex-col items-center gap-2 text-gray-600 mt-2">
          <p>为了更好的找房体验</p>
          <p>移动端功能全部迁移到小程序，</p>
          <p>“地图搜租房”</p>
          <p>关注【人生删除指南】微信公众号，</p>
          <p>获取地址一键进入,</p>
          <p>更多功能更新一秒便知。</p>
        </div>
      </div>
    </Modal>
  );
}
