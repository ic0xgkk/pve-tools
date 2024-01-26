# graceful_shutdown

To solve the problem that Proxmox VE can not set the shutdown method such as VMware, 
you can use this python script and Proxmox VE VM and LXC tags, options to save 
and achieve this target.

You can use custom VM or LXC shutdown method in exec this python script.
It's very helpful when your UPS offline, it can trigger VM or LXC shutdown with timeout, stop or suspend to disk.

To use this script, you should:
* Set your VM or LXC startup order.
* Set your VM or LXC shutdown timeout.
* Set your VM or LXC tag such as:
    * VM
        * `off-method_shutdown`
        * `off-method_stop`
        * `off-method_suspend`
    * LXC
        * `off-method_shutdown`
        * `off-method_stop`
