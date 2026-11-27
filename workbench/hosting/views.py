from workbench import generic


class SiteContactDeleteView(generic.DeleteView):
    def get_success_url(self):
        return self.object.site.get_absolute_url()
