class ContentConsumeListener:
    # interface
    #
    #        void contentConsumed(int len, boolean resume);
    #

    @classmethod
    def call(cls, lis, length, resume):
        if isinstance(lis, ContentConsumeListener):
            lis.content_consumed(length, resume)
        else:
            lis(length, resume)


    dev_null = lambda length, resume: None

