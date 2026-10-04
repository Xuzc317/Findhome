import { Modal } from "antd";
import styles from "./styles.module.css";
import { useNavigate } from "react-router-dom";
import { useCities } from "@/hook/cities";

export function CitiesModal(props: { visible: boolean; onClick?: (city: string) => void; onClose?: () => void }) {
  const { visible } = props;
  const navigate = useNavigate();
  const cities = useCities();
  if (!cities) return null;
  return (
    <Modal open={visible} footer={null} width={500} onClose={props.onClose} onCancel={props.onClose}>
      <div className={styles.cities}>
        {cities.map((item) => (
          <div
            key={item.id}
            className={styles.city}
            onClick={() => {
              if (props.onClick) {
                props.onClick(item.city);
                return;
              }
              const search = window.location.search;
              const params = new URLSearchParams(search);
              params.set("city", item.city);
              navigate(`/houses-list?${params.toString()}`);
              props.onClose && props.onClose();
            }}
          >
            {item.city}
          </div>
        ))}
      </div>
    </Modal>
  );
}
