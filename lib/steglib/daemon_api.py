import json
from steglib.engine import PackageEngine
from steglib.manager import PackageManager
from steglib.lifecycle import LifecycleManager, MultipleInstancesError
from steglib.mapper import DriveMapper
from steglib.group_init import GroupInitializer

class ActionDispatcher:
    def __init__(self):
        self._controllers = {}

    def register(self, prefix, controller):
        self._controllers[prefix] = controller

    def dispatch(self, action, args, interactive_cb, send):
        prefix, sep, method = action.partition(".")
        if not sep or prefix not in self._controllers:
            raise ValueError(f"Unknown action prefix: {prefix}")
        controller = self._controllers[prefix]
        if not hasattr(controller, method):
            raise ValueError(f"Unknown method '{method}' for prefix '{prefix}'")
        return getattr(controller, method)(args, interactive_cb, send)

class PackageController:
    def install(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.install(
            args.get("packages", []), args.get("repo"), args.get("config"),
            args.get("reconfigure", False), args.get("non_interactive", False),
            args.get("id"), interactive_cb
        )

    def reconfigure(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.reconfigure(args.get("instance_ids", []), interactive_cb)

    def remove(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.remove(args.get("instance_ids", []), args.get("purge", False), args.get("cascade", False), interactive_cb)

    def upgrade(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.upgrade(args.get("instance_ids", []), interactive_cb)

    def update(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.update()

    def list(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        return manager.list_packages()

    def clean(self, args, interactive_cb, send):
        manager = PackageManager(PackageEngine(args.get("group"), interactive_cb))
        manager.clean(args.get("yes", False), interactive_cb)

class LifecycleController:
    def execute(self, args, interactive_cb, send):
        act = args.get("ctl_action")
        package_name = args.get("package")
        if_created = args.get("if_created", False)
        verbose = args.get("verbose", False)
        follow = args.get("follow", False)
        
        manager = LifecycleManager(args.get("group"), interactive_cb)
        
        def do_execute(pkg):
            try:
                if act == "restart":
                    manager.execute("stop", pkg, if_created, verbose, follow=False)
                    manager.execute("start", pkg, if_created, verbose, follow=False)
                else:
                    return manager.execute(act, pkg, if_created, verbose, follow=follow)
            except MultipleInstancesError as e:
                choices = ["All instances"] + e.instances
                ans = interactive_cb(f"Multiple instances match '{pkg}'", prompt_type="select", choices=choices, default=None)
                if not ans:
                    raise RuntimeError("Aborted")
                if ans == "All instances":
                    results = {}
                    for inst in e.instances:
                        res = do_execute(inst)
                        if isinstance(res, dict):
                            results.update(res)
                    return results
                else:
                    return do_execute(ans)
                    
        return do_execute(package_name)

class GroupController:
    def init(self, args, interactive_cb, send):
        interactive = args.get("interactive", False)
        initializer = GroupInitializer()
        initializer.initialize(
            device=args.get("device"),
            group_name=args.get("label"),
            domain=args.get("domain"),
            timezone=args.get("timezone"),
            force=args.get("force", False)
        )

class MapController:
    def execute(self, args, interactive_cb, send):
        map_act = args.get("map_action")
        mapper = DriveMapper()
        if map_act == "mount":
            mapper.mount_all()
        elif map_act == "unmount":
            mapper.unmount_all()
        else:
            raise ValueError(f"Unknown map action: {map_act}")

def create_dispatcher():
    dispatcher = ActionDispatcher()
    dispatcher.register("pkg", PackageController())
    dispatcher.register("ctl", LifecycleController())
    dispatcher.register("group", GroupController())
    dispatcher.register("map", MapController())
    return dispatcher
