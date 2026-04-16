import {
  Group,
  Panel,
  Separator,
} from "react-resizable-panels";
import { SidebarLeft } from "./SidebarLeft";
import { SidebarRight } from "./SidebarRight";
import { Viewport } from "./Viewport";

export function MainLayout() {
  return (
    <Group orientation="horizontal" className="flex-1">
      <Panel defaultSize={20} minSize={15} collapsible>
        <SidebarLeft />
      </Panel>

      <Separator className="w-1 bg-border hover:bg-primary transition-colors" />

      <Panel defaultSize={60} minSize={40}>
        <Viewport />
      </Panel>

      <Separator className="w-1 bg-border hover:bg-primary transition-colors" />

      <Panel defaultSize={20} minSize={15} collapsible>
        <SidebarRight />
      </Panel>
    </Group>
  );
}
