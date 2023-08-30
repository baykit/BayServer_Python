from bayserver_docker_http.h2.header_block import HeaderBlock


class HeaderBlockBuilder:
    def build_header_block(self, name, value, tbl):
        idx_list = tbl.get_idx_list(name)
        blk = None

        for idx in idx_list:
            kv = tbl.get(idx)
            if kv is not None and value == kv.value:
                blk = HeaderBlock()
                blk.op = HeaderBlock.INDEX
                blk.index = idx
                break

        if blk is None:
            blk = HeaderBlock()
            if len(idx_list) > 0:
                blk.op = HeaderBlock.KNOWN_HEADER
                blk.index = idx_list[0]
                blk.value = value
            else:
                blk.op = HeaderBlock.UNKNOWN_HEADER
                blk.name = name
                blk.value = value

        return blk

    def build_status_block(self, status, tbl):
        st_index = -1

        status_index_list = tbl.get(":status")
        for index in status_index_list:
            kv = tbl.get(index)
            if kv is not None and status == int(kv.value):
                st_index = index
                break

        blk = HeaderBlock()
        if st_index == -1:
            blk.op = HeaderBlock.INDEX
            blk.index = st_index
        else:
            blk.op = HeaderBlock.KNOWN_HEADER
            blk.index = status_index_list[0]
            blk.value = status.to_i

        return blk