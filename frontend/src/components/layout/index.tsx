import Header from "@/components/header";
import styles from "./layout.module.css";
import Menus from "../menus";

const BaseLayout = ({
  children,
  headerLeft,
}: Readonly<{
  children: React.ReactNode;
  headerLeft?: React.ReactNode;
}>) => {
  return (
    <div className={styles.container}>
      <Header headerLeft={headerLeft} />
      <div className="flex-1 flex">
        <Menus />
        <div className="flex-1 flex flex-col px-10">{children}</div>
      </div>
    </div>
  );
};

export default BaseLayout;
