### Application overview and purpose

The App NetApp Storage Application is a StarlingX native application that provides NetApp ONTAP storage integration through the Trident CSI driver. This application enables Kubernetes workloads to dynamically provision and manage persistent volumes backed by NetApp storage systems.

### Installation instructions

- Application Upload
```bash
system application-upload /usr/local/share/applications/helm/netapp-storage-<version>.tgz
```
Wait for the application upload complete

- NetApp Configuration through user overrides
```bash
# create user overrides
cat <<EOF > netapp-overrides.yaml
backends:
  - name: "ontap-nas"
    protocol: nfs
    managementLIF: "<backend_management_ip_address>"
    dataLIF: "<backend_data_ip_address>"
    svm: "svm_blue"
    credentials:
      secret_name: backend-tbc-secret

storageClasses:
  - name: netapp-nas-backend
    parameters:
      backendType: "ontap-nas"
    mountOptions:
      - rw
      - hard
      - intr
      - bg
      - vers=4
      - proto=tcp
      - timeo=600
      - rsize=65536
      - wsize=65536

snapshotClasses:
  - name: csi-snapclass
    deletionPolicy: Delete

secret:
  - metadata:
      name: backend-tbc-secret
    type: Opaque
    stringData:
      username: "<username>"
      password: "<password>"
EOF

# update user uverrides
system helm-override-update netapp-storage netapp-trident-provisioner trident --values netapp-overrides.yaml
```

- Application Apply
```bash
system application-apply netapp-storage
```

- Once application is applied, check netapp trident pods & backend.
```bash
# check pods
[sysadmin@controller-0 ~(keystone_admin)]$ kubectl get po -n trident
NAME                                  READY   STATUS    RESTARTS         AGE
trident-controller-657cfd989d-gfq4q   5/5     Running   0                22h
trident-node-linux-cqq69              2/2     Running   0                22h
trident-operator-774b6c5568-xcvtg     1/1     Running   0                22h

# check backend
[sysadmin@controller-0 ~(keystone_admin)]$ kubectl get tridentbackend -n trident
NAME        BACKEND     BACKEND UUID
tbe-g82qz   ontap-nas   2fbc80cd-6933-4efc-84c6-0550ac99309d
[sysadmin@controller-0 ~(keystone_admin)]$ kubectl get tbc -n trident
NAME        BACKEND NAME   BACKEND UUID                           PHASE   STATUS
ontap-nas   ontap-nas      2fbc80cd-6933-4efc-84c6-0550ac99309d   Bound   Success
```

### Usage examples

- PVC Creation
```bash
cat <<EOF > rwo-claim1.yaml
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: rwo-test-claim1
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: netapp-nas-backend
EOF
kubectl apply -f rwo-claim1.yaml

cat <<EOF > rwo-claim2.yaml
kind: PersistentVolumeClaim
apiVersion: v1
metadata:
  name: rwo-test-claim2
spec:
  accessModes:
  - ReadWriteOnce
  resources:
    requests:
      storage: 1Gi
  storageClassName: netapp-nas-backend
EOF
kubectl apply -f rwo-claim2.yaml
```

- Check PVC's
```bash
[sysadmin@controller-0 ~(keystone_admin)]$ kubectl get pvc
NAME                 STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS         VOLUMEATTRIBUTESCLASS   AGE
rwo-test-claim1      Bound    pvc-21837d6b-e909-4846-87ec-4a4950c87c27   1Gi        RWO            netapp-nas-backend   <unset>                 43h
rwo-test-claim2      Bound    pvc-875f2ca8-08f7-42a0-80bd-858875d18b27   1Gi        RWO            netapp-nas-backend   <unset>                 43h
```

- Create a user application pod configuring the volumes to be mounted using the created pvc's
```bash
cat <<EOF > rwo-busybox.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: rwo-busybox
  namespace: default
spec:
  progressDeadlineSeconds: 600
  replicas: 1
  selector:
    matchLabels:
      run: busybox
  template:
    metadata:
      labels:
        run: busybox
    spec:
      nodeSelector:
        kubernetes.io/hostname: controller-0
      containers:
      - args:
        - sh
        image: busybox
        imagePullPolicy: Always
        name: busybox
        stdin: true
        tty: true
        volumeMounts:
        - name: pvc1
          mountPath: "/mnt1"
        - name: pvc2
          mountPath: "/mnt2"
      restartPolicy: Always
      volumes:
      - name: pvc1
        persistentVolumeClaim:
          claimName: rwo-test-claim1
      - name: pvc2
        persistentVolumeClaim:
          claimName: rwo-test-claim2
EOF
kubectl apply -f rwo-busybox.yaml
```

- Once the user application pod is running, check if the volumes were successfully mounted.
```bash

[sysadmin@controller-0 ~(keystone_admin)]$ kubectl attach rwo-busybox-6b849668f9-ghn2z -c busybox -i -t
If you don't see a command prompt, try pressing enter.
/ #
```

- Use the 'df' command to check mounted volumes
```bash
/ # df
Filesystem           1K-blocks      Used Available Use% Mounted on
overlay               31441920   7832220  23609700  25% /
tmpfs                    65536         0     65536   0% /dev
tmpfs                  4947324         0   4947324   0% /sys/fs/cgroup
192.168.57.105:/trident_pvc_6dbf555e_536b_46e7_96e9_98e7207d4ba2
                       1048576       256   1048320   0% /mnt1
192.168.57.105:/trident_pvc_b0fad5af_e1ec_4728_a08c_79d4bd84fb02
                       1048576       256   1048320   0% /mnt2
/dev/mapper/cgts--vg-kubelet--lv
                      10218772      1360   9676740   0% /etc/hosts
/dev/mapper/cgts--vg-kubelet--lv
                      10218772      1360   9676740   0% /dev/termination-log
/dev/mapper/cgts--vg-docker--lv
                      31441920   7832220  23609700  25% /etc/hostname
/dev/mapper/cgts--vg-docker--lv
                      31441920   7832220  23609700  25% /etc/resolv.conf
shm                      65536         0     65536   0% /dev/shm
tmpfs                  3033848        12   3033836   0% /var/run/secrets/kubernetes.io/serviceaccount
tmpfs                  4947324         0   4947324   0% /proc/acpi
tmpfs                    65536         0     65536   0% /proc/kcore
tmpfs                    65536         0     65536   0% /proc/keys
tmpfs                    65536         0     65536   0% /proc/timer_list
tmpfs                  4947324         0   4947324   0% /proc/scsi
tmpfs                  4947324         0   4947324   0% /sys/firmware
/ #
```